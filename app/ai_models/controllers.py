from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.config import get_settings
from app.core.security import Principal, require_permissions
from app.ai_models.dependencies import get_db, get_principal
from app.ai_models.schemas import AIModelCreate, AIModelResponse, AIModelUpdate
from app.ai_models.services import AIModelService
from app.shared.schemas import PaginatedResponse


router = APIRouter(prefix="/ai-models", tags=["ai-models"])


@router.post("", response_model=AIModelResponse, dependencies=[Depends(require_permissions("ai_model:create"))])
def create_ai_model(payload: AIModelCreate, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AIModelService(db, principal)
    return service.create(payload.model_dump())


@router.get("", response_model=PaginatedResponse[AIModelResponse], dependencies=[Depends(require_permissions("ai_model:read"))])
def list_ai_models(
    type: Optional[str] = None,
    category: Optional[str] = None,
    enabled: Optional[bool] = None,
    limit: int = Query(default=get_settings().default_page_size, ge=1, le=get_settings().max_page_size),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
    principal: Principal = Depends(get_principal),
):
    service = AIModelService(db, principal)
    items, total = service.list(type=type, category=category, enabled=enabled, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/types", dependencies=[Depends(require_permissions("ai_model:read"))])
def list_types(db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AIModelService(db, principal)
    return service.list_types()


@router.get("/{model_id}", response_model=AIModelResponse, dependencies=[Depends(require_permissions("ai_model:read"))])
def get_ai_model(model_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AIModelService(db, principal)
    return service.get(str(model_id))


@router.patch("/{model_id}", response_model=AIModelResponse, dependencies=[Depends(require_permissions("ai_model:update"))])
def update_ai_model(model_id: UUID, payload: AIModelUpdate, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AIModelService(db, principal)
    return service.update(str(model_id), payload.model_dump(exclude_unset=True))


@router.delete("/{model_id}", status_code=204, dependencies=[Depends(require_permissions("ai_model:delete"))])
def delete_ai_model(model_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AIModelService(db, principal)
    service.delete(str(model_id))
    return None


@router.post("/{model_id}/test-connection", dependencies=[Depends(require_permissions("ai_model:test"))])
def test_connection(model_id: UUID, timeout_s: Optional[int] = None, smoke_inference: bool = False, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AIModelService(db, principal)
    return service.test_connection(str(model_id), timeout_s=timeout_s, smoke_inference=smoke_inference)


@router.post("/{model_id}/enable", response_model=AIModelResponse, dependencies=[Depends(require_permissions("ai_model:enable"))])
def enable_ai_model(model_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AIModelService(db, principal)
    return service.set_enabled(str(model_id), True)


@router.post("/{model_id}/disable", response_model=AIModelResponse, dependencies=[Depends(require_permissions("ai_model:disable"))])
def disable_ai_model(model_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = AIModelService(db, principal)
    return service.set_enabled(str(model_id), False)



