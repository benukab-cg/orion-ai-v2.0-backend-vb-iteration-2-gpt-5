from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException
from fastapi import status

from app.core.config import get_settings
from app.core.security import Principal, require_permissions
from app.agent_tools.dependencies import get_db, get_principal
from app.agent_tools.schemas import (
    AgentToolCreate,
    AgentToolResponse,
    AgentToolUpdate,
    AgentToolInvokeRequest,
)
from app.agent_tools.services import AgentToolService
from app.shared.schemas import PaginatedResponse


router = APIRouter(prefix="/agent-tools", tags=["agent-tools"])


@router.post("", response_model=AgentToolResponse, dependencies=[Depends(require_permissions("tool:create"))])
def create_tool(payload: AgentToolCreate, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentToolService(db, principal)
    try:
        return service.create(payload.model_dump())
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=PaginatedResponse[AgentToolResponse], dependencies=[Depends(require_permissions("tool:read"))])
def list_tools(
    kind: Optional[str] = None,
    enabled: Optional[bool] = None,
    limit: int = Query(default=get_settings().default_page_size, ge=1, le=get_settings().max_page_size),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
    principal: Principal = Depends(get_principal),
):
    service = AgentToolService(db, principal)
    items, total = service.list(kind=kind, enabled=enabled, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/kinds", dependencies=[Depends(require_permissions("tool:read"))])
def list_kinds(db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentToolService(db, principal)
    return service.list_kinds()


@router.get("/{tool_id}", response_model=AgentToolResponse, dependencies=[Depends(require_permissions("tool:read"))])
def get_tool(tool_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentToolService(db, principal)
    return service.get(str(tool_id))


@router.patch("/{tool_id}", response_model=AgentToolResponse, dependencies=[Depends(require_permissions("tool:update"))])
def update_tool(tool_id: UUID, payload: AgentToolUpdate, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentToolService(db, principal)
    try:
        return service.update(str(tool_id), payload.model_dump(exclude_unset=True))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{tool_id}", status_code=204, dependencies=[Depends(require_permissions("tool:delete"))])
def delete_tool(tool_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentToolService(db, principal)
    service.delete(str(tool_id))
    return None


@router.post("/{tool_id}/enable", response_model=AgentToolResponse, dependencies=[Depends(require_permissions("tool:enable"))])
def enable_tool(tool_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentToolService(db, principal)
    return service.set_enabled(str(tool_id), True)


@router.post("/{tool_id}/disable", response_model=AgentToolResponse, dependencies=[Depends(require_permissions("tool:disable"))])
def disable_tool(tool_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentToolService(db, principal)
    return service.set_enabled(str(tool_id), False)


@router.post("/{tool_id}/invoke", dependencies=[Depends(require_permissions("tool:invoke"))])
def invoke_tool(tool_id: UUID, body: AgentToolInvokeRequest, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentToolService(db, principal)
    try:
        return service.invoke(str(tool_id), body.payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


