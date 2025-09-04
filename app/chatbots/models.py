from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Chatbot(Base):
    __tablename__ = "chatbot"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visibility: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # private | org | public

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    agent_network_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_network.id", ondelete="RESTRICT"), nullable=False)
    agent_network_version: Mapped[str] = mapped_column(String(32), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_chatbot_tenant_name"),
        UniqueConstraint("tenant_id", "slug", name="uq_chatbot_tenant_slug"),
        Index("ix_chatbot_tenant_enabled", "tenant_id", "is_enabled"),
    )


class ChatThread(Base):
    __tablename__ = "chat_thread"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    chatbot_id: Mapped[str] = mapped_column(String(36), ForeignKey("chatbot.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)

    title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)  # active|archived|deleted
    tags: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    token_usage: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    last_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_thread_chatbot_user", "chatbot_id", "user_id"),
        Index("ix_thread_status", "status"),
        Index("ix_thread_last_message_at", "last_message_at"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_message"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    thread_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_thread.id", ondelete="CASCADE"), nullable=False)

    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user|assistant|system|tool
    content_json: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    citations_json: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    attachments_json: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    token_counts_json: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    error_json: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_message_thread_created", "thread_id", "created_at"),
    )


