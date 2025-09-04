from __future__ import annotations

from typing import Any, Annotated

from langchain_core.messages.ai import AIMessage
from langchain_core.messages.base import BaseMessage
from langchain_core.messages.human import HumanMessage
from langchain_core.messages.tool import ToolMessage
from langchain_core.messages.system import SystemMessage
from sqlalchemy.orm import Session

from langgraph_swarm import create_swarm
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from app.core.security import Principal
from app.agent_networks.schemas import AgentNetworkSpec
from app.agent_networks.exceptions import AgentNetworkInvalid
from app.agents.services import AgentService


def invoke_swarm(db: Session, principal: Principal, spec: AgentNetworkSpec, payload: dict) -> dict:
    if not spec.nodes:
        raise AgentNetworkInvalid("Swarm needs at least one agent node")

    # Build adjacency per policy
    cfg = spec.swarm or {}
    policy = (cfg.get("handoff_policy") or "edges")
    adjacency: dict[str, set[str]] = {n.node_key: set() for n in spec.nodes}
    if policy == "edges":
        for e in spec.edges:
            adjacency.setdefault(e.source_node_key, set()).add(e.target_node_key)
    else:
        keys = [n.node_key for n in spec.nodes]
        for a in keys:
            adjacency[a] = set(k for k in keys if k != a)

    # Create agents
    built_agents = []
    agent_service = AgentService(db, principal)

    # Build destination descriptions for richer handoff tool prompts
    try:
        from sqlalchemy import and_, select
        from app.agents.models import Agent as AgentModel

        agent_ids = [str(n.agent_id) for n in spec.nodes if n.agent_id]
        node_desc_by_key: dict[str, str] = {}
        if agent_ids:
            stmt = select(AgentModel).where(
                and_(
                    AgentModel.tenant_id == principal.tenant_id,
                    AgentModel.deleted_at.is_(None),
                    AgentModel.id.in_(agent_ids),
                )
            )
            id_to_agent = {str(a.id): a for a in db.execute(stmt).scalars().all()}
            for node in spec.nodes:
                if node.agent_id:
                    a = id_to_agent.get(str(node.agent_id))
                    if a is not None:
                        desc = (a.description or a.name or str(a.id))
                        # Keep concise to fit tool description
                        node_desc_by_key[node.node_key] = desc
    except Exception:
        node_desc_by_key = {}
    for node in spec.nodes:
        if not node.agent_id:
            raise AgentNetworkInvalid("Swarm nodes must reference agents")

        # Handoff tools
        handoff_tools = []
        for dest in sorted(adjacency.get(node.node_key, set())):
            rich_desc = node_desc_by_key.get(dest)
            if rich_desc:
                description = f"Transfer conversation to {dest}. {rich_desc}"
            else:
                description = f"Transfer conversation to {dest}"
            handoff_tools.append(_create_context_handoff_tool(agent_name=dest, description=description, source_name=node.node_key))

        # Build from AgentService to centralize agent/tool config
        built = agent_service.build_langchain_agent(str(node.agent_id), extra_tools=handoff_tools, name=node.node_key)
        built_agents.append(built)

    default_active = (cfg.get("default_active_agent") or spec.nodes[0].node_key)
    swarm = create_swarm(agents=built_agents, default_active_agent=default_active).compile()

    # Execute
    messages = payload.get("messages")
    input_text = payload.get("input")
    if not messages and input_text is not None:
        messages = [HumanMessage(content=str(input_text))]
    result = swarm.invoke({"messages": messages or []})

    # Normalize output to plain text
    def _coerce_text(obj: Any) -> str:
        try:
            if obj is None:
                return ""
            if isinstance(obj, str):
                return obj
            if isinstance(obj, BaseMessage):
                return str(getattr(obj, "content", "") or "")
            if isinstance(obj, list):
                # Try to find last AI message
                for msg in reversed(obj):
                    if isinstance(msg, BaseMessage):
                        if isinstance(msg, AIMessage):
                            return str(getattr(msg, "content", "") or "")
                # Fallback: join stringified items
                return "\n".join(str(it) for it in obj if it is not None)
            if isinstance(obj, dict):
                # Common shape: {"messages": [...]} or nested
                msgs = obj.get("messages") if hasattr(obj, "get") else None
                if isinstance(msgs, list):
                    for msg in reversed(msgs):
                        if isinstance(msg, BaseMessage) and isinstance(msg, AIMessage):
                            return str(getattr(msg, "content", "") or "")
                # Fallback to string
                return str(obj)
            return str(obj)
        except Exception:
            return str(obj)

    output_text = _coerce_text(result)
    return {"output": output_text}


def _create_context_handoff_tool(*, agent_name: str, description: str | None, source_name: str):
    """Create a handoff tool that carries recent user context to the destination agent.

    Appends a tool message noting the transfer and a synthesized user message summarizing the last user query.
    """
    from typing import Annotated
    from langchain_core.tools import tool, InjectedToolCallId
    from langgraph.prebuilt import InjectedState
    from langgraph.types import Command

    name = f"transfer_to_{agent_name}"
    tool_desc = description or f"Transfer conversation to {agent_name}"

    @tool(name, description=tool_desc)
    def handoff_tool(state: Annotated[dict, InjectedState], tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
        """Transfer conversation to {agent_name}. {tool_desc}"""
        messages = state.get("messages", []) if isinstance(state, dict) else []
        
        # Create ToolMessage for this handoff
        tool_message = ToolMessage(
            content=f"Transferred from {source_name} to {agent_name}",
            name=name,
            tool_call_id=tool_call_id,
        )
        
        # Find last user message content to forward as context
        last_user_text = None
        for msg in reversed(messages):
            try:
                if isinstance(msg, HumanMessage):
                    content = msg.content
                    if isinstance(content, str) and content.strip():
                        last_user_text = content.strip()
                        break
            except Exception:
                continue
        
        # Create context for the destination agent
        if last_user_text:
            system_msg = SystemMessage(
                content=(
                    f"You are {agent_name}. Respond directly to the user's question. "
                    f"If the request involves multiple topics, address all relevant aspects you can help with. "
                    f"Provide a helpful response and end with: 'If you want me to go deeper on any area, tell me which.'"
                )
            )
            forward_msg = HumanMessage(
                content=(
                    f"Context from {source_name}: The user asked: '{last_user_text}'.\n"
                    f"Please provide a comprehensive answer addressing all relevant aspects."
                )
            )
            new_messages = messages + [tool_message, system_msg, forward_msg]
        else:
            new_messages = messages + [tool_message]

        return Command(goto=agent_name, update={"messages": new_messages}, graph=Command.PARENT)

    return handoff_tool
