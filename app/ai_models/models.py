from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AIModel(Base):
    __tablename__ = "ai_model"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tags: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)

    config: Mapped["AIModelConfig"] = relationship("AIModelConfig", back_populates="ai_model", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_ai_model_tenant_name"),
        Index("ix_ai_model_tenant_type", "tenant_id", "type"),
        Index("ix_ai_model_tenant_enabled", "tenant_id", "is_enabled"),
    )


class AIModelConfig(Base):
    __tablename__ = "ai_model_config"

    ai_model_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_model.id", ondelete="CASCADE"), primary_key=True)

    config_encrypted: Mapped[bytes] = mapped_column()
    config_schema_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    redaction_map: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    ai_model: Mapped[AIModel] = relationship("AIModel", back_populates="config")



