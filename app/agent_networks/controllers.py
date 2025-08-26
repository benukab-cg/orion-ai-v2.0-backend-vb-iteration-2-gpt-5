from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException
from fastapi import status

from app.core.config import get_settings
from app.core.security import Principal, require_permissions
from app.agent_networks.dependencies import get_db, get_principal
from app.agent_networks.schemas import (
    AgentNetworkCreate,
    AgentNetworkResponse,
    AgentNetworkUpdate,
    AgentNetworkInvokeRequest,
)
from app.agent_networks.services import AgentNetworkService
from app.shared.schemas import PaginatedResponse


router = APIRouter(prefix="/agent-networks", tags=["agent-networks"])


@router.post("", response_model=AgentNetworkResponse, dependencies=[Depends(require_permissions("agent_network:create"))])
def create_network(payload: AgentNetworkCreate, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentNetworkService(db, principal)
    try:
        return service.create(payload.model_dump())
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=PaginatedResponse[AgentNetworkResponse], dependencies=[Depends(require_permissions("agent_network:read"))])
def list_networks(
    type: Optional[str] = None,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    enabled: Optional[bool] = None,
    limit: int = Query(default=get_settings().default_page_size, ge=1, le=get_settings().max_page_size),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
    principal: Principal = Depends(get_principal),
):
    service = AgentNetworkService(db, principal)
    items, total = service.list(type=type, status=status_filter, enabled=enabled, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{network_id}", response_model=AgentNetworkResponse, dependencies=[Depends(require_permissions("agent_network:read"))])
def get_network(network_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentNetworkService(db, principal)
    return service.get(str(network_id))


@router.patch("/{network_id}", response_model=AgentNetworkResponse, dependencies=[Depends(require_permissions("agent_network:update"))])
def update_network(network_id: UUID, payload: AgentNetworkUpdate, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentNetworkService(db, principal)
    try:
        return service.update(str(network_id), payload.model_dump(exclude_unset=True))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{network_id}", status_code=204, dependencies=[Depends(require_permissions("agent_network:delete"))])
def delete_network(network_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentNetworkService(db, principal)
    service.delete(str(network_id))
    return None


@router.post("/{network_id}/validate", dependencies=[Depends(require_permissions("agent_network:validate"))])
def validate_network(network_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentNetworkService(db, principal)
    try:
        return service.validate(str(network_id))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{network_id}/invoke", dependencies=[Depends(require_permissions("agent_network:invoke"))])
def invoke_network(network_id: UUID, body: AgentNetworkInvokeRequest, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AgentNetworkService(db, principal)
    try:
        return service.invoke(str(network_id), body.model_dump(exclude_none=True))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))



