from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException
from fastapi import status

from app.core.config import get_settings
from app.core.security import Principal, require_permissions
from app.chatbots.dependencies import get_db, get_principal
from app.chatbots.schemas import (
    ChatbotCreate,
    ChatbotResponse,
    ChatbotUpdate,
    ChatbotInvokeRequest,
    ChatThreadCreate,
    ChatThreadUpdate,
    ChatThreadResponse,
    ChatMessageCreate,
)
from app.chatbots.services import ChatbotService, ChatThreadService
from app.shared.schemas import PaginatedResponse


router = APIRouter(prefix="/chatbots", tags=["chatbots"])


@router.post("", response_model=ChatbotResponse, dependencies=[Depends(require_permissions("chatbot:create"))])
def create_chatbot(payload: ChatbotCreate, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = ChatbotService(db, principal)
    try:
        return service.create(payload.model_dump())
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=PaginatedResponse[ChatbotResponse], dependencies=[Depends(require_permissions("chatbot:read"))])
def list_chatbots(
    enabled: Optional[bool] = None,
    limit: int = Query(default=get_settings().default_page_size, ge=1, le=get_settings().max_page_size),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
    principal: Principal = Depends(get_principal),
):
    service = ChatbotService(db, principal)
    items, total = service.list(enabled=enabled, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{chatbot_id}", response_model=ChatbotResponse, dependencies=[Depends(require_permissions("chatbot:read"))])
def get_chatbot(chatbot_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = ChatbotService(db, principal)
    return service.get(str(chatbot_id))


@router.patch("/{chatbot_id}", response_model=ChatbotResponse, dependencies=[Depends(require_permissions("chatbot:update"))])
def update_chatbot(chatbot_id: UUID, payload: ChatbotUpdate, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = ChatbotService(db, principal)
    try:
        return service.update(str(chatbot_id), payload.model_dump(exclude_unset=True))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{chatbot_id}", status_code=204, dependencies=[Depends(require_permissions("chatbot:delete"))])
def delete_chatbot(chatbot_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = ChatbotService(db, principal)
    service.delete(str(chatbot_id))
    return None


@router.post("/{chatbot_id}/enable", response_model=ChatbotResponse, dependencies=[Depends(require_permissions("chatbot:enable"))])
def enable_chatbot(chatbot_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = ChatbotService(db, principal)
    return service.set_enabled(str(chatbot_id), True)


@router.post("/{chatbot_id}/disable", response_model=ChatbotResponse, dependencies=[Depends(require_permissions("chatbot:disable"))])
def disable_chatbot(chatbot_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = ChatbotService(db, principal)
    return service.set_enabled(str(chatbot_id), False)


@router.post("/{chatbot_id}/invoke", dependencies=[Depends(require_permissions("chatbot:invoke"))])
def invoke_chatbot(chatbot_id: UUID, body: ChatbotInvokeRequest, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = ChatbotService(db, principal)
    try:
        return service.invoke(str(chatbot_id), body.model_dump(exclude_none=True))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{chatbot_id}/threads", response_model=ChatThreadResponse, dependencies=[Depends(require_permissions("thread:create"))])
def create_thread(chatbot_id: UUID, payload: ChatThreadCreate, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = ChatThreadService(db, principal)
    return service.create(str(chatbot_id), payload.model_dump(exclude_none=True))


@router.get("/{chatbot_id}/threads", dependencies=[Depends(require_permissions("thread:read"))])
def list_threads(chatbot_id: UUID, status: Optional[str] = None, limit: int = Query(default=get_settings().default_page_size, ge=1, le=get_settings().max_page_size), offset: int = Query(default=0, ge=0), db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = ChatThreadService(db, principal)
    items, total = service.list(str(chatbot_id), status=status, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{chatbot_id}/threads/{thread_id}", response_model=ChatThreadResponse, dependencies=[Depends(require_permissions("thread:read"))])
def get_thread(chatbot_id: UUID, thread_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = ChatThreadService(db, principal)
    return service.get(str(chatbot_id), str(thread_id))


@router.patch("/{chatbot_id}/threads/{thread_id}", response_model=ChatThreadResponse, dependencies=[Depends(require_permissions("thread:update"))])
def update_thread(chatbot_id: UUID, thread_id: UUID, payload: ChatThreadUpdate, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = ChatThreadService(db, principal)
    return service.update(str(chatbot_id), str(thread_id), payload.model_dump(exclude_unset=True))


@router.delete("/{chatbot_id}/threads/{thread_id}", status_code=204, dependencies=[Depends(require_permissions("thread:delete"))])
def delete_thread(chatbot_id: UUID, thread_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = ChatThreadService(db, principal)
    service.delete(str(chatbot_id), str(thread_id))
    return None


@router.post("/{chatbot_id}/threads/{thread_id}/archive", response_model=ChatThreadResponse, dependencies=[Depends(require_permissions("thread:update"))])
def archive_thread(chatbot_id: UUID, thread_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = ChatThreadService(db, principal)
    return service.archive(str(chatbot_id), str(thread_id))


@router.post("/{chatbot_id}/threads/{thread_id}/restore", response_model=ChatThreadResponse, dependencies=[Depends(require_permissions("thread:update"))])
def restore_thread(chatbot_id: UUID, thread_id: UUID, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = ChatThreadService(db, principal)
    return service.restore(str(chatbot_id), str(thread_id))


@router.post("/{chatbot_id}/threads/{thread_id}/messages", dependencies=[Depends(require_permissions("message:create"))])
def create_user_message(chatbot_id: UUID, thread_id: UUID, payload: ChatMessageCreate, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = ChatThreadService(db, principal)
    return service.create_user_message(str(chatbot_id), str(thread_id), payload.content)


@router.get("/{chatbot_id}/threads/{thread_id}/messages", dependencies=[Depends(require_permissions("message:read"))])
def list_messages(chatbot_id: UUID, thread_id: UUID, limit: int = Query(default=get_settings().default_page_size, ge=1, le=get_settings().max_page_size), offset: int = Query(default=0, ge=0), db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = ChatThreadService(db, principal)
    items, total = service.list_messages(str(chatbot_id), str(thread_id), limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("/{chatbot_id}/threads/{thread_id}/invoke", dependencies=[Depends(require_permissions("chatbot:invoke"))])
def invoke_thread(chatbot_id: UUID, thread_id: UUID, body: ChatbotInvokeRequest, db=Depends(get_db), principal: Principal = Depends(get_principal)):
    service = ChatThreadService(db, principal)
    return service.invoke(str(chatbot_id), str(thread_id), body.model_dump(exclude_none=True))


