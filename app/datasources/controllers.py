from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.config import get_settings
from app.core.security import Principal, require_permissions
from app.datasources.dependencies import get_db, get_principal
from app.datasources.schemas import DataSourceCreate, DataSourceResponse, DataSourceUpdate
from app.datasources.services import DataSourceService
from app.shared.schemas import PaginatedResponse


router = APIRouter(prefix="/datasources", tags=["datasources"])


@router.post("", response_model=DataSourceResponse, dependencies=[Depends(require_permissions("datasource:create"))])
def create_datasource(payload: DataSourceCreate, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DataSourceService(db, principal)
    return service.create(payload.model_dump())


@router.get("", response_model=PaginatedResponse[DataSourceResponse], dependencies=[Depends(require_permissions("datasource:read"))])
def list_datasources(
    type: Optional[str] = None,
    enabled: Optional[bool] = None,
    tag: Optional[str] = None,
    limit: int = Query(default=get_settings().default_page_size, ge=1, le=get_settings().max_page_size),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
    principal: Principal = Depends(get_principal),
):
    service = DataSourceService(db, principal)
    items, total = service.list(type=type, enabled=enabled, tag=tag, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/types", dependencies=[Depends(require_permissions("datasource:read"))])
def list_types(db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DataSourceService(db, principal)
    return service.list_types()


@router.get("/{ds_id}", response_model=DataSourceResponse, dependencies=[Depends(require_permissions("datasource:read"))])
def get_datasource(ds_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DataSourceService(db, principal)
    return service.get(str(ds_id))


@router.patch("/{ds_id}", response_model=DataSourceResponse, dependencies=[Depends(require_permissions("datasource:update"))])
def update_datasource(ds_id: UUID, payload: DataSourceUpdate, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DataSourceService(db, principal)
    return service.update(str(ds_id), payload.model_dump(exclude_unset=True))


@router.delete("/{ds_id}", status_code=204, dependencies=[Depends(require_permissions("datasource:delete"))])
def delete_datasource(ds_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DataSourceService(db, principal)
    service.delete(str(ds_id))
    return None


@router.post("/{ds_id}/test-connection", dependencies=[Depends(require_permissions("datasource:test"))])
def test_connection(ds_id: UUID, timeout_s: Optional[int] = None, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DataSourceService(db, principal)
    return service.test_connection(str(ds_id), timeout_s=timeout_s)


@router.post("/{ds_id}/enable", response_model=DataSourceResponse, dependencies=[Depends(require_permissions("datasource:enable"))])
def enable_datasource(ds_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DataSourceService(db, principal)
    return service.set_enabled(str(ds_id), True)


@router.post("/{ds_id}/disable", response_model=DataSourceResponse, dependencies=[Depends(require_permissions("datasource:disable"))])
def disable_datasource(ds_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DataSourceService(db, principal)
    return service.set_enabled(str(ds_id), False)


