from __future__ import annotations

from typing import Any, Optional

from langchain_core.tools import StructuredTool
import json as _json


class AgentToolAdapter:
    kind: str
    provider: Optional[str] = None
    display_name: str = ""
    version: str = "1.0"

    def validate_config(self, config: dict) -> None:
        return None

    def validate_bindings(self, bindings: dict | None) -> None:
        return None

    def invoke(self, *, tool: dict, payload: dict, context: dict) -> Any:  # pragma: no cover - implemented by concrete adapters
        raise NotImplementedError

    # LangGraph/LangChain integration: default generic tool wrapper
    def as_langchain_tool(self, *, tool: dict, context: dict) -> StructuredTool:
        """Return a LangChain StructuredTool for this adapter.

        Default implementation exposes a generic JSON payload interface and delegates to service.invoke.
        Concrete adapters may override to provide typed signatures.
        """
        tool_id: str = tool["id"]
        description: str = (tool.get("description") or "Agent tool").strip()

        def _call(payload: dict | str | None = None):
            args = payload
            if isinstance(args, str):
                try:
                    args = _json.loads(args)
                except Exception:
                    args = {}
            # Lazy import to avoid circular import during module init
            from app.agent_tools.services import AgentToolService  # noqa: WPS433
            svc = AgentToolService(context["db"], context["principal"])
            return svc.invoke(tool_id, args or {})

        name_base = tool.get("name") or f"tool_{tool_id[:8]}"
        safe_name = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in name_base)[:63]
        return StructuredTool.from_function(name=safe_name, description=description, func=_call)


