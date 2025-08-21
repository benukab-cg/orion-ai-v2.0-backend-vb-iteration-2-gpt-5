from __future__ import annotations

from typing import Any

from app.agent_tools.adapters import registry
from app.agent_tools.adapters.base import AgentToolAdapter
from langchain_core.tools import StructuredTool
from typing import Optional, List
from app.agent_tools.exceptions import AgentToolBindingInvalid
from app.datasets.services import DatasetService


class SqlSelectAdapter(AgentToolAdapter):
    kind = "sql.select"
    display_name = "SQL Select Tool"

    def validate_bindings(self, bindings: dict | None) -> None:
        resources = (bindings or {}).get("resources", [])
        primary = next((r for r in resources if r.get("role") == "primary" and r.get("type") == "dataset"), None)
        if not primary:
            raise AgentToolBindingInvalid("sql.select requires a dataset binding with role 'primary'")

    def invoke(self, *, tool: dict, payload: dict, context: dict) -> Any:
        resources = (tool.get("bindings") or {}).get("resources", [])
        primary = next(r for r in resources if r.get("role") == "primary" and r.get("type") == "dataset")

        config = tool.get("config") or {}
        default_columns = config.get("default_columns")
        max_rows = int(config.get("max_rows", 500))
        query_timeout_s = int(config.get("query_timeout_s", 15))
        allowed_predicates = set(config.get("allowed_predicates") or [])

        # Merge payload with defaults and enforce caps
        columns = payload.get("columns") or default_columns
        limit = payload.get("limit")
        if limit is None:
            limit = max_rows
        else:
            limit = min(int(limit), max_rows)

        query_spec = {
            "columns": columns,
            "where": payload.get("where"),
            "params": payload.get("params"),
            "order_by": payload.get("order_by"),
            "limit": limit,
            "offset": payload.get("offset", 0),
            "timeout_s": min(max(query_timeout_s, 1), 60),
        }

        # Basic gate for allowed_predicates (non-parsing: rely on dataset layer for strict param safety)
        if allowed_predicates and isinstance(query_spec.get("where"), dict):
            for key in query_spec["where"].keys():
                if key not in allowed_predicates:
                    raise AgentToolBindingInvalid(f"Predicate on disallowed column: {key}")

        # Delegate to dataset SQL select
        ds_service = DatasetService(context["db"], context["principal"])
        return ds_service.sql_select(primary["id"], query_spec)

    def as_langchain_tool(self, *, tool: dict, context: dict) -> StructuredTool:
        resources = (tool.get("bindings") or {}).get("resources", [])
        primary = next((r for r in resources if r.get("role") == "primary" and r.get("type") == "dataset"), None)
        description = (tool.get("description") or "SQL Select tool").strip()
        tool_id: str = tool["id"]

        def _call(
            columns: Optional[List[str]] = None,
            where: Optional[dict] = None,
            params: Optional[dict] = None,
            order_by: Optional[List[str]] = None,
            limit: Optional[int] = None,
            offset: Optional[int] = None,
        ):
            payload = {
                "columns": columns,
                "where": where,
                "params": params,
                "order_by": order_by,
                "limit": limit,
                "offset": offset,
            }
            # Delegate via context service to enforce RLS and RBAC
            from app.agent_tools.services import AgentToolService
            svc = AgentToolService(context["db"], context["principal"])
            return svc.invoke(tool_id, {k: v for k, v in payload.items() if v is not None})

        name_base = tool.get("name") or f"tool_{tool_id[:8]}"
        safe_name = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in name_base)[:63]
        return StructuredTool.from_function(name=safe_name, description=description, func=_call)


registry.register(SqlSelectAdapter.kind, SqlSelectAdapter())


