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
    })


def require_permissions(*required: str):
    def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not set(required).issubset(principal.permissions):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return principal

    return dependency


