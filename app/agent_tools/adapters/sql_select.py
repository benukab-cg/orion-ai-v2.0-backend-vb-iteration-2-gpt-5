from __future__ import annotations

from typing import Any

from app.agent_tools.adapters import registry
from app.agent_tools.adapters.base import AgentToolAdapter
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


registry.register(SqlSelectAdapter.kind, SqlSelectAdapter())


