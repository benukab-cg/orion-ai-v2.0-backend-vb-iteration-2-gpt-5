from __future__ import annotations

import time
import uuid
from typing import Any, Optional, List

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import Principal
from app.agents.exceptions import AgentConflict, AgentDisabled, AgentNotFound, AgentConfigInvalid
from app.agents.models import Agent, AgentConfig
from app.ai_models.models import AIModel
from app.ai_models.utils import decrypt_config
from app.ai_models.adapters import registry as ai_model_registry
from app.agent_tools.models import AgentTool

# LangGraph imports (MVP single-agent graph)
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage
from typing import TypedDict


class AgentService:
    def __init__(self, db: Session, principal: Principal) -> None:
        self.db = db
        self.principal = principal
        self.settings = get_settings()

    # CRUD
    def create(self, payload: dict) -> dict:
        self._validate_create_payload(payload)

        agent_id = str(uuid.uuid4())
        obj = Agent(
            id=agent_id,
            tenant_id=self.principal.tenant_id,
            owner_id=self.principal.user_id,
            name=payload["name"].strip(),
            type=(payload.get("type") or "langgraph.single").strip(),
            description=(payload.get("description") or None),
            tags=payload.get("tags") or None,
            ai_model_id=payload["ai_model_id"],
            is_enabled=bool(payload.get("is_enabled", True)),
            bindings=self._normalize_bindings(payload.get("bindings") or None),
            created_by=self.principal.user_id,
            updated_by=self.principal.user_id,
        )
        cfg = AgentConfig(
            agent_id=agent_id,
            config_json=payload.get("config") or {},
            config_schema_version=payload.get("config_schema_version"),
        )
        self._validate_config_semantics(cfg.config_json)
        obj.config = cfg

        self.db.add(obj)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise AgentConflict("An agent with this name already exists in the tenant")
        self.db.refresh(obj)
        return self._to_response_dict(obj)

    def get(self, agent_id: str) -> dict:
        obj = self._get_owned(agent_id)
        return self._to_response_dict(obj)

    def list(self, *, type: Optional[str] = None, enabled: Optional[bool] = None, limit: int = 20, offset: int = 0) -> tuple[list[dict], int]:
        stmt = select(Agent).where(
            and_(
                Agent.tenant_id == self.principal.tenant_id,
                Agent.deleted_at.is_(None),
            )
        )
        if type:
            stmt = stmt.where(Agent.type == type)
        if enabled is not None:
            stmt = stmt.where(Agent.is_enabled == enabled)

        total = self.db.execute(stmt).scalars().unique().all()
        items = total[offset : offset + limit]
        return [self._to_response_dict(m) for m in items], len(total)

    def update(self, agent_id: str, payload: dict) -> dict:
        obj = self._get_owned(agent_id)

        if "name" in payload and payload["name"]:
            obj.name = payload["name"].strip()
        if "description" in payload:
            obj.description = payload["description"]
        if "tags" in payload:
            obj.tags = payload["tags"]
        if "ai_model_id" in payload and payload["ai_model_id"]:
            self._ensure_llm_model(payload["ai_model_id"])  # validate exists and is llm
            obj.ai_model_id = payload["ai_model_id"]
        if "is_enabled" in payload and payload["is_enabled"] is not None:
            obj.is_enabled = bool(payload["is_enabled"])
        if "bindings" in payload:
            self._ensure_tools_exist(payload.get("bindings") or None)
            obj.bindings = self._normalize_bindings(payload.get("bindings") or None)
        obj.updated_by = self.principal.user_id

        if "config" in payload and payload["config"] is not None:
            self._validate_config_semantics(payload["config"])
            obj.config.config_json = payload["config"]
            obj.config.config_schema_version = payload.get("config_schema_version") or obj.config.config_schema_version

        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise AgentConflict("An agent with this name already exists in the tenant")
        self.db.refresh(obj)
        return self._to_response_dict(obj)

    def delete(self, agent_id: str) -> None:
        obj = self._get_owned(agent_id)
        from datetime import datetime as _dt

        obj.deleted_at = _dt.utcnow()
        self.db.commit()

    def set_enabled(self, agent_id: str, enabled: bool) -> dict:
        obj = self._get_owned(agent_id)
        obj.is_enabled = enabled
        obj.updated_by = self.principal.user_id
        self.db.commit()
        self.db.refresh(obj)
        return self._to_response_dict(obj)

    def validate(self, agent_id: str) -> dict:
        obj = self._get_owned(agent_id)
        self._ensure_llm_model(obj.ai_model_id)
        self._ensure_tools_exist(obj.bindings or None)
        self._validate_config_semantics(obj.config.config_json)
        return {"status": "ok"}

    # Invocation (single-agent LangGraph-like loop)
    def invoke(self, agent_id: str, payload: dict) -> dict:
        obj = self._get_owned(agent_id)
        if not obj.is_enabled:
            raise AgentDisabled()

        # Load LLM connector
        llm_model = self._ensure_llm_model(obj.ai_model_id, ensure_enabled=True)
        connector = ai_model_registry.get(llm_model.type)
        if connector is None:
            raise AgentConfigInvalid("LLM connector not implemented")
        cfg = decrypt_config(llm_model.config.config_encrypted)

        # Prepare prompt and runtime options
        config = obj.config.config_json or {}
        prompt_template: str = (config.get("prompt_template") or "").strip()
        input_text: str = (payload.get("input") or "").strip()
        variables: dict = payload.get("variables") or {}
        rendered_prompt = self._render_prompt(prompt_template, input_text, variables)

        tool_policy = (config.get("tool_policy") or {}) | (payload.get("tool_overrides") or {})
        llm_params = (config.get("llm_params") or {}) | (payload.get("llm_overrides") or {})
        runtime_limits = config.get("runtime_limits") or {}
        max_steps = int(runtime_limits.get("max_steps", 16))

        # Simple single-step or bounded loop with no real graph persistence
        steps = 0
        tool_calls = 0
        start = time.time()
        final_output: Any = None

        # Execute via LangGraph prebuilt ReAct agent with optional tool-calling
        result = self._run_langgraph_react(cfg, rendered_prompt, llm_params, obj, payload.get("tool_overrides") or {})
        steps = result.get("steps", 1)
        final_output = result.get("output")

        latency_ms = int((time.time() - start) * 1000)
        return {
            "output": final_output,
            "steps": steps,
            "tool_calls": result.get("tool_calls", 0),
            "tokens": result.get("tokens", {}),
            "latency_ms": latency_ms,
            "finish_reason": result.get("finish_reason", "stop"),
        }

    # Helpers
    def _get_owned(self, agent_id: str) -> Agent:
        stmt = select(Agent).where(
            and_(
                Agent.id == agent_id,
                Agent.tenant_id == self.principal.tenant_id,
                Agent.deleted_at.is_(None),
            )
        )
        obj = self.db.execute(stmt).scalar_one_or_none()
        if obj is None:
            raise AgentNotFound()
        return obj

    def _to_response_dict(self, obj: Agent) -> dict:
        return {
            "id": obj.id,
            "tenant_id": obj.tenant_id,
            "owner_id": obj.owner_id,
            "name": obj.name,
            "type": obj.type,
            "description": obj.description,
            "tags": obj.tags,
            "ai_model_id": obj.ai_model_id,
            "is_enabled": obj.is_enabled,
            "bindings": obj.bindings,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
            "created_by": obj.created_by,
            "updated_by": obj.updated_by,
            "config": obj.config.config_json,
            "config_schema_version": obj.config.config_schema_version,
        }

    def _normalize_bindings(self, bindings: dict | None) -> dict | None:
        if not bindings:
            return None
        tools = []
        for tid in (bindings.get("tools") or []):
            tools.append(str(tid))
        return {"tools": tools}

    def _ensure_llm_model(self, ai_model_id: str, *, ensure_enabled: bool = False) -> AIModel:
        stmt = select(AIModel).where(
            and_(
                AIModel.id == ai_model_id,
                AIModel.tenant_id == self.principal.tenant_id,
                AIModel.deleted_at.is_(None),
            )
        )
        mdl = self.db.execute(stmt).scalar_one_or_none()
        if mdl is None:
            raise AgentConfigInvalid("Referenced AI model not found in tenant")
        if mdl.category != "llm":
            raise AgentConfigInvalid("Agent requires an LLM category model")
        if ensure_enabled and not mdl.is_enabled:
            raise AgentConfigInvalid("Referenced AI model is disabled")
        return mdl

    def _ensure_tools_exist(self, bindings: dict | None) -> None:
        tool_ids = [str(t) for t in (bindings or {}).get("tools", [])]
        if not tool_ids:
            return
        stmt = select(AgentTool.id).where(
            and_(
                AgentTool.tenant_id == self.principal.tenant_id,
                AgentTool.deleted_at.is_(None),
                AgentTool.is_enabled.is_(True),
                AgentTool.id.in_(tool_ids),
            )
        )
        found = {row[0] for row in self.db.execute(stmt).all()}
        missing = [tid for tid in tool_ids if tid not in found]
        if missing:
            raise AgentConfigInvalid(f"Unknown/disabled tools referenced: {', '.join(missing)}")

    def _validate_create_payload(self, payload: dict) -> None:
        self._ensure_llm_model(payload["ai_model_id"])  # exists + is llm
        self._ensure_tools_exist(payload.get("bindings") or None)
        self._validate_config_semantics(payload.get("config") or {})

    def _validate_config_semantics(self, cfg: dict) -> None:
        # Basic bounds and types per requirements
        limits = cfg.get("runtime_limits") or {}
        ms = int(limits.get("max_steps", 16))
        if ms < 1 or ms > 64:
            raise AgentConfigInvalid("runtime_limits.max_steps out of bounds")
        dur = int(limits.get("max_duration_s", 60))
        if dur < 1 or dur > 300:
            raise AgentConfigInvalid("runtime_limits.max_duration_s out of bounds")
        tp = cfg.get("tool_policy") or {}
        mtc = int(tp.get("max_tool_calls", 8))
        if mtc < 0 or mtc > 32:
            raise AgentConfigInvalid("tool_policy.max_tool_calls out of bounds")

    def _render_prompt(self, template: str, input_text: str, variables: dict) -> str:
        rendered = template.replace("{{input}}", input_text)
        # Simple dot-path replacement for variables {{variables.key}}
        for k, v in (variables or {}).items():
            rendered = rendered.replace(f"{{{{variables.{k}}}}}", str(v))
        return rendered

    def _llm_chat(self, connector, config: dict, prompt: str, params: dict) -> dict:
        if not hasattr(connector, "chat"):
            raise AgentConfigInvalid("LLM connector does not support chat invocation")
        system = "You are a helpful AI agent."
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        return connector.chat(config, messages=messages, params=params or {})

    # LangGraph runner using prebuilt ReAct agent and tool-calling
    def _run_langgraph_react(self, config: dict, prompt: str, params: dict, agent: Agent, tool_overrides: dict) -> dict:
        # Build a LangChain OpenAI chat model using our stored connection config
        # Note: We expect OpenAI-compatible settings in AI Model config
        api_key = config.get("api_key")
        base_url = config.get("base_url")
        model_name = (params or {}).get("model") or config.get("default_model") or "gpt-4o-mini"
        temperature = float((params or {}).get("temperature", 0))

        chat = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key,
            base_url=base_url,
        )

        # Wrap our bound Agent Tools via their adapters (no per-kind ifs here)
        from langchain_core.tools import StructuredTool
        from app.agent_tools.adapters import registry as tool_registry
        from app.agent_tools.services import AgentToolService  # ensure name available if adapters import indirectly

        svc = AgentToolService(self.db, self.principal)
        tools: list[StructuredTool] = []
        bindings = agent.bindings or {}
        policy = (agent.config.config_json.get("tool_policy") or {})
        # Apply overrides if provided
        if tool_overrides and tool_overrides.get("allowed_tools") is not None:
            policy = {**policy, "allowed_tools": tool_overrides.get("allowed_tools")}
        allowed_field = policy.get("allowed_tools", None)
        if allowed_field is None:
            # Null → allow any bound tools
            allowed_set = set(str(t) for t in (bindings.get("tools") or []))
        else:
            # [] → allow none; [ids] → allow only listed
            allowed_set = set(str(t) for t in (allowed_field or []))
        # Compute tool ids in allowed_set (may be empty)
        bound_ids = [str(t) for t in (bindings.get("tools") or [])]
        tool_ids = [tid for tid in bound_ids if tid in allowed_set]

        # Load tool metadata for richer descriptions
        tool_meta: dict[str, AgentTool] = {}
        if tool_ids:
            stmt = select(AgentTool).where(
                and_(
                    AgentTool.tenant_id == self.principal.tenant_id,
                    AgentTool.deleted_at.is_(None),
                    AgentTool.id.in_(tool_ids),
                )
            )
            for obj in self.db.execute(stmt).scalars().all():
                tool_meta[str(obj.id)] = obj

        def _make_tool(tid: str):
            obj = tool_meta.get(tid)
            if not obj:
                return None
            adapter = tool_registry.get(obj.kind, obj.provider)
            if not adapter:
                return None
            # Build context for adapter
            ctx = {"db": self.db, "principal": self.principal, "settings": self.settings}
            # adapter.as_langchain_tool expects the full tool dict like our service returns
            tool_dict = {
                "id": obj.id,
                "name": obj.name,
                "description": obj.description,
                "bindings": obj.bindings,
                "config": obj.config.config_json,
            }
            return adapter.as_langchain_tool(tool=tool_dict, context=ctx)

        for tid in tool_ids:
            t = _make_tool(tid)
            if t is not None:
                tools.append(t)

        # Create the prebuilt ReAct agent
        agent_graph = create_react_agent(
            model=chat,
            tools=tools,
            prompt=(agent.config.config_json or {}).get("prompt_template") or "You are a helpful AI agent.",
            checkpointer=InMemorySaver(),
        )

        state = agent_graph.invoke({"messages": [{"role": "user", "content": prompt}]}, config={"configurable": {"thread_id": str(uuid.uuid4())}})
        # Extract final assistant message and count tool calls across the whole transcript
        messages = state.get("messages", []) if isinstance(state, dict) else []
        tool_call_count = 0

        def _coerce_text(content: Any) -> str:
            if content is None:
                return ""
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts: list[str] = []
                for it in content:
                    try:
                        # LangChain content parts often have .type and .text or dict with 'text'
                        text_val = getattr(it, "text", None)
                        if text_val is None and isinstance(it, dict):
                            text_val = it.get("text") or it.get("content")
                        if isinstance(text_val, str):
                            parts.append(text_val)
                        else:
                            parts.append(str(it))
                    except Exception:
                        parts.append(str(it))
                return "\n".join([p for p in parts if p])
            return str(content)

        output: str = ""
        # First pass: count tool calls across all messages
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role")
                if role == "tool":
                    tool_call_count += 1
                elif role in ("assistant", "ai"):
                    tcs = msg.get("tool_calls")
                    if isinstance(tcs, list):
                        tool_call_count += len(tcs)
            elif isinstance(msg, BaseMessage):
                if isinstance(msg, ToolMessage):
                    tool_call_count += 1
                elif isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                    try:
                        tool_call_count += len(msg.tool_calls)
                    except Exception:
                        pass

        # Second pass: pick the last assistant/ai message as output
        for msg in reversed(messages):
            if isinstance(msg, dict):
                if msg.get("role") in ("assistant", "ai"):
                    output = _coerce_text(msg.get("content"))
                    break
            elif isinstance(msg, BaseMessage):
                if isinstance(msg, AIMessage):
                    output = _coerce_text(msg.content)
                    break
        return {"output": output, "tokens": {}, "finish_reason": "stop", "steps": 1, "tool_calls": tool_call_count}



