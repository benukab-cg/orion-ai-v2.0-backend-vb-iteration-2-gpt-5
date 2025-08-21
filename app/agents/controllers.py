from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException
from fastapi import status

from app.core.config import get_settings
from app.core.security import Principal, require_permissions
from app.agents.dependencies import get_db, get_principal
from app.agents.schemas import AgentCreate, AgentResponse, AgentUpdate, AgentInvokeRequest
from app.agents.services import AgentService
from app.shared.schemas import PaginatedResponse


router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentResponse, dependencies=[Depends(require_permissions("agent:create"))])
def create_agent(payload: AgentCreate, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentService(db, principal)
    try:
        return service.create(payload.model_dump())
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=PaginatedResponse[AgentResponse], dependencies=[Depends(require_permissions("agent:read"))])
def list_agents(
    type: Optional[str] = None,
    enabled: Optional[bool] = None,
    limit: int = Query(default=get_settings().default_page_size, ge=1, le=get_settings().max_page_size),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
    principal: Principal = Depends(get_principal),
):
    service = AgentService(db, principal)
    items, total = service.list(type=type, enabled=enabled, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{agent_id}", response_model=AgentResponse, dependencies=[Depends(require_permissions("agent:read"))])
def get_agent(agent_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentService(db, principal)
    return service.get(str(agent_id))


@router.patch("/{agent_id}", response_model=AgentResponse, dependencies=[Depends(require_permissions("agent:update"))])
def update_agent(agent_id: UUID, payload: AgentUpdate, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentService(db, principal)
    try:
        return service.update(str(agent_id), payload.model_dump(exclude_unset=True))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{agent_id}", status_code=204, dependencies=[Depends(require_permissions("agent:delete"))])
def delete_agent(agent_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentService(db, principal)
    service.delete(str(agent_id))
    return None


@router.post("/{agent_id}/enable", response_model=AgentResponse, dependencies=[Depends(require_permissions("agent:enable"))])
def enable_agent(agent_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentService(db, principal)
    return service.set_enabled(str(agent_id), True)


@router.post("/{agent_id}/disable", response_model=AgentResponse, dependencies=[Depends(require_permissions("agent:disable"))])
def disable_agent(agent_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentService(db, principal)
    return service.set_enabled(str(agent_id), False)


@router.post("/{agent_id}/validate", dependencies=[Depends(require_permissions("agent:validate"))])
def validate_agent(agent_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentService(db, principal)
    try:
        return service.validate(str(agent_id))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{agent_id}/invoke", dependencies=[Depends(require_permissions("agent:invoke"))])
def invoke_agent(agent_id: UUID, body: AgentInvokeRequest, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentService(db, principal)
    try:
        return service.invoke(str(agent_id), body.model_dump(exclude_none=True))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))



