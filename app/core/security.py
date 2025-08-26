from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from fastapi import Depends, HTTPException, status


@dataclass
class Principal:
    user_id: str
    tenant_id: str
    permissions: set[str]


def get_current_principal() -> Principal:  # Stub for now
    # In production, extract from auth token/session
    # For development, return a permissive principal within a default tenant
    return Principal(user_id="dev-user", tenant_id="dev-tenant", permissions={
        "datasource:create",
        "datasource:read",
        "datasource:update",
        "datasource:delete",
        "datasource:test",
        "datasource:enable",
        "datasource:disable",
        # AI Models full access (for development/testing)
        "ai_model:create",
        "ai_model:read",
        "ai_model:update",
        "ai_model:delete",
        "ai_model:test",
        "ai_model:enable",
        "ai_model:disable",
        # Datasets CRUD
        "dataset:create",
        "dataset:read",
        "dataset:update",
        "dataset:delete",
        "dataset:enable",
        "dataset:disable",
        # Dataset data-plane (read-only)
        "dataset_data:select",
        "dataset_data:schema",
        "dataset_data:stats",
        "dataset_data:query",
        "dataset_data:get",
        "dataset_data:presign_get",
        # Agent Tools (development default: full access)
        "tool:create",
        "tool:read",
        "tool:update",
        "tool:delete",
        "tool:enable",
        "tool:disable",
        "tool:invoke",
        # Agents (development default: full access)
        "agent:create",
        "agent:read",
        "agent:update",
        "agent:delete",
        "agent:enable",
        "agent:disable",
        "agent:validate",
        "agent:invoke",
        # Agent Networks (development default: full access)
        "agent_network:*",
        "agent_network:create",
        "agent_network:read",
        "agent_network:update",
        "agent_network:delete",
        "agent_network:validate",
        "agent_network:invoke",
        # Global admin wildcard (dev only)
        "*",
    })


def require_permissions(*required: str):
    def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        perms = principal.permissions or set()
        if "*" in perms:
            return principal
        # accept category wildcards like "agent_network:*"
        needed: set[str] = set()
        for r in required:
            if r in perms:
                continue
            cat = r.split(":", 1)[0] if ":" in r else r
            if f"{cat}:*" in perms:
                continue
            needed.add(r)
        if needed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return principal

    return dependency


