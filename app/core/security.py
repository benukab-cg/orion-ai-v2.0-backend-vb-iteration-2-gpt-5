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
    })


def require_permissions(*required: str):
    def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not set(required).issubset(principal.permissions):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return principal

    return dependency


