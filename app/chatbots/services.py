from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import Principal
from app.chatbots.models import Chatbot, ChatThread, ChatMessage
from app.chatbots.exceptions import ChatbotConflict, ChatbotInvalid, ChatbotNotFound
from app.agent_networks.models import AgentNetwork
from app.agent_networks.services import AgentNetworkService


class ChatbotService:
    def __init__(self, db: Session, principal: Principal) -> None:
        self.db = db
        self.principal = principal

    # CRUD
    def create(self, payload: dict) -> dict:
        self._validate_create_payload(payload)

        bot_id = str(uuid.uuid4())
        obj = Chatbot(
            id=bot_id,
            tenant_id=self.principal.tenant_id,
            owner_id=self.principal.user_id,
            name=payload["name"].strip(),
            slug=payload["slug"].strip(),
            description=(payload.get("description") or None),
            visibility=(payload.get("visibility") or None),
            is_enabled=bool(payload.get("is_enabled", True)),
            agent_network_id=payload["agent_network_id"],
            agent_network_version=payload["agent_network_version"],
            created_by=self.principal.user_id,
            updated_by=self.principal.user_id,
        )
        self.db.add(obj)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ChatbotConflict("A chatbot with this name or slug already exists in the tenant")
        self.db.refresh(obj)
        return self._to_response_dict(obj)

    def get(self, chatbot_id: str) -> dict:
        obj = self._get_owned(chatbot_id)
        return self._to_response_dict(obj)

    def list(self, *, enabled: Optional[bool] = None, limit: int = 20, offset: int = 0) -> tuple[list[dict], int]:
        stmt = select(Chatbot).where(
            and_(
                Chatbot.tenant_id == self.principal.tenant_id,
                Chatbot.deleted_at.is_(None),
            )
        )
        if enabled is not None:
            stmt = stmt.where(Chatbot.is_enabled == enabled)
        all_items = self.db.execute(stmt).scalars().unique().all()
        items = all_items[offset : offset + limit]
        return [self._to_response_dict(m) for m in items], len(all_items)

    def update(self, chatbot_id: str, payload: dict) -> dict:
        obj = self._get_owned(chatbot_id)

        if "name" in payload and payload["name"]:
            obj.name = payload["name"].strip()
        if "slug" in payload and payload["slug"]:
            obj.slug = payload["slug"].strip()
        if "description" in payload:
            obj.description = payload["description"]
        if "visibility" in payload:
            obj.visibility = payload["visibility"]
        if "is_enabled" in payload and payload["is_enabled"] is not None:
            obj.is_enabled = bool(payload["is_enabled"])
        if "agent_network_id" in payload and payload["agent_network_id"]:
            obj.agent_network_id = payload["agent_network_id"]
        if "agent_network_version" in payload and payload["agent_network_version"]:
            obj.agent_network_version = payload["agent_network_version"]
        obj.updated_by = self.principal.user_id

        # Validate binding if either field changed
        if any(k in payload for k in ("agent_network_id", "agent_network_version")):
            self._ensure_network_binding(obj.agent_network_id, obj.agent_network_version)

        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ChatbotConflict("A chatbot with this name or slug already exists in the tenant")
        self.db.refresh(obj)
        return self._to_response_dict(obj)

    def delete(self, chatbot_id: str) -> None:
        obj = self._get_owned(chatbot_id)
        from datetime import datetime as _dt

        obj.deleted_at = _dt.utcnow()
        self.db.commit()

    def set_enabled(self, chatbot_id: str, enabled: bool) -> dict:
        obj = self._get_owned(chatbot_id)
        obj.is_enabled = enabled
        obj.updated_by = self.principal.user_id
        self.db.commit()
        self.db.refresh(obj)
        return self._to_response_dict(obj)

    # Execution (ephemeral; no thread_id in this iteration)
    def invoke(self, chatbot_id: str, payload: dict) -> dict:
        obj = self._get_owned(chatbot_id)
        if not obj.is_enabled:
            raise ChatbotInvalid("Chatbot is disabled")
        # Validate binding and active status
        self._ensure_network_binding(obj.agent_network_id, obj.agent_network_version)

        # Delegate invocation to Agent Network
        network_svc = AgentNetworkService(self.db, self.principal)
        # Pass through thread_id if present; Agent Network will use it for memory
        payload = dict(payload or {})
        result = network_svc.invoke(obj.agent_network_id, payload)
        return result

    # Helpers (ChatbotService)
    def _get_owned(self, chatbot_id: str) -> Chatbot:
        stmt = select(Chatbot).where(
            and_(
                Chatbot.id == chatbot_id,
                Chatbot.tenant_id == self.principal.tenant_id,
                Chatbot.deleted_at.is_(None),
            )
        )
        obj = self.db.execute(stmt).scalar_one_or_none()
        if obj is None:
            raise ChatbotNotFound()
        return obj

    def _to_response_dict(self, obj: Chatbot) -> dict:
        return {
            "id": obj.id,
            "tenant_id": obj.tenant_id,
            "owner_id": obj.owner_id,
            "name": obj.name,
            "slug": obj.slug,
            "description": obj.description,
            "visibility": obj.visibility,
            "is_enabled": obj.is_enabled,
            "agent_network_id": obj.agent_network_id,
            "agent_network_version": obj.agent_network_version,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
            "created_by": obj.created_by,
            "updated_by": obj.updated_by,
        }

    def _validate_create_payload(self, payload: dict) -> None:
        if not payload.get("name"):
            raise ChatbotInvalid("name is required")
        if not payload.get("slug"):
            raise ChatbotInvalid("slug is required")
        if not payload.get("agent_network_id") or not payload.get("agent_network_version"):
            raise ChatbotInvalid("agent_network_id and agent_network_version are required")
        self._ensure_network_binding(payload["agent_network_id"], payload["agent_network_version"])

    def _ensure_network_binding(self, network_id: str, version: str) -> None:
        stmt = select(AgentNetwork).where(
            and_(
                AgentNetwork.id == network_id,
                AgentNetwork.tenant_id == self.principal.tenant_id,
                AgentNetwork.deleted_at.is_(None),
                AgentNetwork.is_enabled.is_(True),
                AgentNetwork.version == version,
            )
        )
        obj = self.db.execute(stmt).scalar_one_or_none()
        if obj is None:
            raise ChatbotInvalid("Referenced agent network id/version not found or not enabled")
        if (obj.status or "draft") == "deprecated":
            raise ChatbotInvalid("Referenced agent network version is deprecated")


class ChatThreadService:
    def __init__(self, db: Session, principal: Principal) -> None:
        self.db = db
        self.principal = principal

    # Threads CRUD
    def create(self, chatbot_id: str, payload: dict) -> dict:
        chatbot = ChatbotService(self.db, self.principal)._get_owned(chatbot_id)
        thread_id = str(uuid.uuid4())
        obj = ChatThread(
            id=thread_id,
            tenant_id=self.principal.tenant_id,
            chatbot_id=chatbot.id,
            user_id=self.principal.user_id,
            title=(payload.get("title") or None),
            status="active",
            tags=(payload.get("tags") or None),
        )
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return self._thread_to_dict(obj)

    def get(self, chatbot_id: str, thread_id: str) -> dict:
        obj = self._get_owned_thread(chatbot_id, thread_id)
        return self._thread_to_dict(obj)

    def list(self, chatbot_id: str, *, status: Optional[str] = None, limit: int = 20, offset: int = 0) -> tuple[list[dict], int]:
        self._ensure_chatbot_owned(chatbot_id)
        stmt = select(ChatThread).where(
            and_(
                ChatThread.tenant_id == self.principal.tenant_id,
                ChatThread.chatbot_id == chatbot_id,
                ChatThread.user_id == self.principal.user_id,
            )
        )
        if status:
            stmt = stmt.where(ChatThread.status == status)
        all_items = self.db.execute(stmt).scalars().unique().all()
        items = all_items[offset : offset + limit]
        return [self._thread_to_dict(m) for m in items], len(all_items)

    def update(self, chatbot_id: str, thread_id: str, payload: dict) -> dict:
        obj = self._get_owned_thread(chatbot_id, thread_id)
        if "title" in payload:
            obj.title = payload["title"]
        if "status" in payload and payload["status"] in ("active", "archived"):
            obj.status = payload["status"]
        if "tags" in payload:
            obj.tags = payload["tags"]
        self.db.commit()
        self.db.refresh(obj)
        return self._thread_to_dict(obj)

    def delete(self, chatbot_id: str, thread_id: str) -> None:
        obj = self._get_owned_thread(chatbot_id, thread_id)
        from datetime import datetime as _dt
        obj.status = "deleted"
        obj.deleted_at = _dt.utcnow()
        self.db.commit()

    def archive(self, chatbot_id: str, thread_id: str) -> dict:
        return self.update(chatbot_id, thread_id, {"status": "archived"})

    def restore(self, chatbot_id: str, thread_id: str) -> dict:
        return self.update(chatbot_id, thread_id, {"status": "active"})

    # Messages and invocation
    def create_user_message(self, chatbot_id: str, thread_id: str, content: dict) -> dict:
        thread = self._get_owned_thread(chatbot_id, thread_id)
        msg = ChatMessage(
            id=str(uuid.uuid4()),
            tenant_id=self.principal.tenant_id,
            thread_id=thread.id,
            role="user",
            content_json=content,
        )
        self.db.add(msg)
        from datetime import datetime as _dt
        thread.last_message_at = _dt.utcnow()
        self.db.commit()
        self.db.refresh(msg)
        return self._message_to_dict(msg)

    def list_messages(self, chatbot_id: str, thread_id: str, *, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
        thread = self._get_owned_thread(chatbot_id, thread_id)
        stmt = select(ChatMessage).where(
            and_(
                ChatMessage.tenant_id == self.principal.tenant_id,
                ChatMessage.thread_id == thread.id,
            )
        ).order_by(ChatMessage.created_at.asc())
        all_items = self.db.execute(stmt).scalars().unique().all()
        items = all_items[offset : offset + limit]
        return [self._message_to_dict(m) for m in items], len(all_items)

    def invoke(self, chatbot_id: str, thread_id: str, payload: dict) -> dict:
        thread = self._get_owned_thread(chatbot_id, thread_id)
        # Create user message
        user_content = payload.get("content") or {"text": payload.get("input")}
        self.create_user_message(chatbot_id, thread_id, user_content)

        # Call Agent Network with thread_id to use agentic memory
        network_svc = AgentNetworkService(self.db, self.principal)
        chatbot = ChatbotService(self.db, self.principal)._get_owned(chatbot_id)
        ChatbotService(self.db, self.principal)._ensure_network_binding(chatbot.agent_network_id, chatbot.agent_network_version)

        req = {
            "thread_id": thread.id,
            "input": payload.get("input"),
            "variables": payload.get("variables") or {},
            "stream": bool(payload.get("stream", False)),
        }
        result = network_svc.invoke(chatbot.agent_network_id, req)

        # Persist assistant message with citations/metadata
        msg = ChatMessage(
            id=str(uuid.uuid4()),
            tenant_id=self.principal.tenant_id,
            thread_id=thread.id,
            role="assistant",
            content_json={"text": result.get("output")},
            citations_json=(result.get("citations") or None),
            run_id=result.get("run_id"),
            token_counts_json=(result.get("tokens") or None),
            latency_ms=result.get("latency_ms"),
        )
        self.db.add(msg)
        from datetime import datetime as _dt
        thread.last_message_at = _dt.utcnow()
        thread.last_run_id = result.get("run_id")
        self.db.commit()
        return {
            "message": self._message_to_dict(msg),
            "result": result,
        }

    # Helpers (ChatThreadService)
    def _ensure_chatbot_owned(self, chatbot_id: str) -> Chatbot:
        svc = ChatbotService(self.db, self.principal)
        return svc._get_owned(chatbot_id)

    def _get_owned_thread(self, chatbot_id: str, thread_id: str) -> ChatThread:
        self._ensure_chatbot_owned(chatbot_id)
        stmt = select(ChatThread).where(
            and_(
                ChatThread.id == thread_id,
                ChatThread.chatbot_id == chatbot_id,
                ChatThread.tenant_id == self.principal.tenant_id,
                ChatThread.user_id == self.principal.user_id,
                ChatThread.status != "deleted",
            )
        )
        obj = self.db.execute(stmt).scalar_one_or_none()
        if obj is None:
            raise ChatbotInvalid("Thread not found or access denied")
        return obj

    def _thread_to_dict(self, obj: ChatThread) -> dict:
        return {
            "id": obj.id,
            "chatbot_id": obj.chatbot_id,
            "user_id": obj.user_id,
            "title": obj.title,
            "status": obj.status,
            "tags": obj.tags,
            "last_message_at": obj.last_message_at,
            "token_usage": obj.token_usage,
            "last_run_id": obj.last_run_id,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }

    def _message_to_dict(self, obj: ChatMessage) -> dict:
        return {
            "id": obj.id,
            "thread_id": obj.thread_id,
            "role": obj.role,
            "content_json": obj.content_json,
            "citations_json": obj.citations_json,
            "run_id": obj.run_id,
            "token_counts_json": obj.token_counts_json,
            "latency_ms": obj.latency_ms,
            "created_at": obj.created_at,
        }

    # end ChatThreadService helpers


