from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass
class RLSEvaluationContext:
    tenant_id: str
    user_id: str
    roles: list[str]
    dataset_id: str
    params: dict | None = None


def evaluate_policies(policies: Iterable[dict], context: RLSEvaluationContext, action: str) -> dict:
    """Evaluate RLS policies in priority order and return a merged filter spec.

    - Deny overrides allow
    - Absent allow implies deny; callers must have explicit allow for action
    - Category-specific filters are merged by the service layer
    """

    allow_filters: list[dict] = []
    any_allow = False
    for p in sorted(policies, key=lambda x: int(x.get("priority", 1000))):
        actions = p.get("actions") or []
        if action not in actions:
            continue
        effect = (p.get("effect") or "").lower()
        if effect == "deny":
            return {"denied": True}
        if effect == "allow":
            any_allow = True
            # Collect category-specific filter fragments
            filt = {}
            if p.get("sql_filter"):
                filt["sql_filter"] = p["sql_filter"]
            if p.get("vector_filter"):
                filt["vector_filter"] = p["vector_filter"]
            if p.get("blob_key_constraint"):
                filt["blob_key_constraint"] = p["blob_key_constraint"]
            allow_filters.append(filt)

    if not any_allow:
        return {"denied": True}

    # Merge filters with AND semantics by category (service layer interprets fields)
    merged: dict[str, Any] = {}
    sql_parts = [f["sql_filter"] for f in allow_filters if "sql_filter" in f]
    if sql_parts:
        merged["sql_filter"] = " AND ".join(f"({s})" for s in sql_parts)
    vector_parts = [f["vector_filter"] for f in allow_filters if "vector_filter" in f]
    if vector_parts:
        merged["vector_filter"] = {"$and": vector_parts}
    blob_parts = [f["blob_key_constraint"] for f in allow_filters if "blob_key_constraint" in f]
    if blob_parts:
        merged["blob_key_constraint"] = blob_parts  # service enforces any-match across allowed constraints
    return merged


