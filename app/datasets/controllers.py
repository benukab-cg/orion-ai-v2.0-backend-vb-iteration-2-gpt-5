from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import get_settings
from app.core.security import Principal, require_permissions
from app.datasets.dependencies import get_db, get_principal
from app.datasets.schemas import (
    BlobGetRequest,
    BlobPresignRequest,
    DatasetCreate,
    DatasetResponse,
    DatasetUpdate,
    SQLSelectRequest,
    VectorQueryRequest,
)
from app.datasets.services import DatasetService
from app.shared.schemas import PaginatedResponse


router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("", response_model=DatasetResponse, dependencies=[Depends(require_permissions("dataset:create"))])
def create_dataset(payload: DatasetCreate, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DatasetService(db, principal)
    return service.create(payload.model_dump())


@router.get("", response_model=PaginatedResponse[DatasetResponse], dependencies=[Depends(require_permissions("dataset:read"))])
def list_datasets(
    category: Optional[str] = None,
    enabled: Optional[bool] = None,
    limit: int = Query(default=get_settings().default_page_size, ge=1, le=get_settings().max_page_size),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
    principal: Principal = Depends(get_principal),
):
    service = DatasetService(db, principal)
    items, total = service.list(category=category, enabled=enabled, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{dataset_id}", response_model=DatasetResponse, dependencies=[Depends(require_permissions("dataset:read"))])
def get_dataset(dataset_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DatasetService(db, principal)
    return service.get(str(dataset_id))


@router.patch("/{dataset_id}", response_model=DatasetResponse, dependencies=[Depends(require_permissions("dataset:update"))])
def update_dataset(dataset_id: UUID, payload: DatasetUpdate, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DatasetService(db, principal)
    return service.update(str(dataset_id), payload.model_dump(exclude_unset=True))


@router.delete("/{dataset_id}", status_code=204, dependencies=[Depends(require_permissions("dataset:delete"))])
def delete_dataset(dataset_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DatasetService(db, principal)
    service.delete(str(dataset_id))
    return None


@router.post("/{dataset_id}/enable", response_model=DatasetResponse, dependencies=[Depends(require_permissions("dataset:enable"))])
def enable_dataset(dataset_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DatasetService(db, principal)
    return service.set_enabled(str(dataset_id), True)


@router.post("/{dataset_id}/disable", response_model=DatasetResponse, dependencies=[Depends(require_permissions("dataset:disable"))])
def disable_dataset(dataset_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DatasetService(db, principal)
    return service.set_enabled(str(dataset_id), False)


# SQL operations
@router.post("/{dataset_id}/sql/select", dependencies=[Depends(require_permissions("dataset_data:select"))])
def sql_select(dataset_id: UUID, payload: SQLSelectRequest, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DatasetService(db, principal)
    return service.sql_select(str(dataset_id), payload.model_dump(exclude_unset=True))


@router.get("/{dataset_id}/sql/schema", dependencies=[Depends(require_permissions("dataset_data:schema"))])
def sql_schema(dataset_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DatasetService(db, principal)
    try:
        return service.sql_schema(str(dataset_id))
    except ValueError as e:
        # Map table not found and similar validation to 404/422
        msg = str(e)
        status_code = 404 if "not found" in msg.lower() else 422
        raise HTTPException(status_code=status_code, detail={"message": msg, "code": "DATASET_VALIDATION_ERROR"})


@router.get("/{dataset_id}/sql/count", dependencies=[Depends(require_permissions("dataset_data:stats"))])
def sql_count(dataset_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DatasetService(db, principal)
    try:
        return service.sql_count(str(dataset_id))
    except ValueError as e:
        msg = str(e)
        status_code = 404 if "not found" in msg.lower() else 422
        raise HTTPException(status_code=status_code, detail={"message": msg, "code": "DATASET_VALIDATION_ERROR"})


# Vector operations
@router.post("/{dataset_id}/vector/query", dependencies=[Depends(require_permissions("dataset_data:query"))])
def vector_query(dataset_id: UUID, payload: VectorQueryRequest, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DatasetService(db, principal)
    return service.vector_query(str(dataset_id), payload.model_dump(exclude_unset=True))


@router.get("/{dataset_id}/vector/stats", dependencies=[Depends(require_permissions("dataset_data:stats"))])
def vector_stats(dataset_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DatasetService(db, principal)
    return service.vector_stats(str(dataset_id))


# Blob operations
@router.get("/{dataset_id}/blob/get", dependencies=[Depends(require_permissions("dataset_data:get"))])
def blob_get(dataset_id: UUID, range_start: Optional[int] = Query(default=None, ge=0), range_end: Optional[int] = Query(default=None, ge=0), db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DatasetService(db, principal)
    range_spec = None
    if range_start is not None or range_end is not None:
        range_spec = {"start": range_start, "end": range_end}
    return service.blob_get(str(dataset_id), range_spec)


@router.post("/{dataset_id}/blob/presign", dependencies=[Depends(require_permissions("dataset_data:presign_get"))])
def blob_presign(dataset_id: UUID, payload: BlobPresignRequest, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = DatasetService(db, principal)
    ttl = payload.ttl_s if payload.ttl_s is not None else 300
    return service.blob_presign(str(dataset_id), ttl)


