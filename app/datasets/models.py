from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Dataset(Base):
    __tablename__ = "dataset"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    data_source_id: Mapped[str] = mapped_column(String(36), ForeignKey("data_source.id", ondelete="RESTRICT"), nullable=False)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)

    config: Mapped["DatasetConfig"] = relationship("DatasetConfig", back_populates="dataset", uselist=False, cascade="all, delete-orphan")
    cached_schema: Mapped[Optional["DatasetCachedSchema"]] = relationship("DatasetCachedSchema", back_populates="dataset", uselist=False, cascade="all, delete-orphan")
    metadata_profile: Mapped[Optional["DatasetMetadataProfile"]] = relationship("DatasetMetadataProfile", back_populates="dataset", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_dataset_tenant_name"),
        Index("ix_dataset_tenant_category", "tenant_id", "category"),
    )


class DatasetConfig(Base):
    __tablename__ = "dataset_config"

    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("dataset.id", ondelete="CASCADE"), primary_key=True)
    config_json: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    config_schema_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    dataset: Mapped[Dataset] = relationship("Dataset", back_populates="config")


class DatasetCachedSchema(Base):
    __tablename__ = "dataset_cached_schema"

    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("dataset.id", ondelete="CASCADE"), primary_key=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_json: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    schema_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    dataset: Mapped[Dataset] = relationship("Dataset", back_populates="cached_schema")


class DatasetMetadataProfile(Base):
    __tablename__ = "dataset_metadata_profile"

    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("dataset.id", ondelete="CASCADE"), primary_key=True)
    fields: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    dataset: Mapped[Dataset] = relationship("Dataset", back_populates="metadata_profile")


class DatasetRLSPolicy(Base):
    __tablename__ = "dataset_rls_policy"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("dataset.id", ondelete="CASCADE"), nullable=False)
    principal_type: Mapped[str] = mapped_column(String(16), nullable=False)  # user|role|tenant|public
    principal_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    actions: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)  # list[str]
    effect: Mapped[str] = mapped_column(String(8), nullable=False)  # allow|deny
    condition: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    sql_filter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vector_filter: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    blob_key_constraint: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    priority: Mapped[int] = mapped_column(nullable=False, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


