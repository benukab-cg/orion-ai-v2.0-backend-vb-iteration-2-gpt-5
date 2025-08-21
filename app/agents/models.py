from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Agent(Base):
    __tablename__ = "agent"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g., "langgraph.single"

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    ai_model_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_model.id", ondelete="RESTRICT"), nullable=False)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    bindings: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)

    config: Mapped["AgentConfig"] = relationship("AgentConfig", back_populates="agent", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_agent_tenant_name"),
        Index("ix_agent_tenant_type", "tenant_id", "type"),
        Index("ix_agent_tenant_enabled", "tenant_id", "is_enabled"),
    )


class AgentConfig(Base):
    __tablename__ = "agent_config"

    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent.id", ondelete="CASCADE"), primary_key=True)
    config_json: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    config_schema_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    agent: Mapped[Agent] = relationship("Agent", back_populates="config", primaryjoin="AgentConfig.agent_id==Agent.id", foreign_keys=[agent_id])



