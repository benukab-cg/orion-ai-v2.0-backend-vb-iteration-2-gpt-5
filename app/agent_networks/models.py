from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AgentNetwork(Base):
    __tablename__ = "agent_network"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)  # standalone | supervised | swarm | custom

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")  # draft | active | deprecated

    spec_json: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)

    nodes: Mapped[list[AgentNetworkNode]] = relationship(
        "AgentNetworkNode",
        back_populates="network",
        cascade="all, delete-orphan",
        foreign_keys=lambda: [AgentNetworkNode.network_id],
        primaryjoin=lambda: AgentNetwork.id == AgentNetworkNode.network_id,
    )
    edges: Mapped[list[AgentNetworkEdge]] = relationship("AgentNetworkEdge", back_populates="network", cascade="all, delete-orphan")
    interface: Mapped[Optional[AgentNetworkInterface]] = relationship("AgentNetworkInterface", back_populates="network", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", "version", name="uq_agent_network_slug_version"),
        Index("ix_agent_network_tenant", "tenant_id"),
        Index("ix_agent_network_status", "tenant_id", "status"),
        Index("ix_agent_network_enabled", "tenant_id", "is_enabled"),
    )


class AgentNetworkNode(Base):
    __tablename__ = "agent_network_node"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    network_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_network.id", ondelete="CASCADE"), nullable=False)
    node_key: Mapped[str] = mapped_column(String(64), nullable=False)

    # Either agent or child network reference
    agent_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("agent.id", ondelete="RESTRICT"), nullable=True)
    child_network_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("agent_network.id", ondelete="RESTRICT"), nullable=True)
    child_network_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # supervisor | worker | router | etc
    config_json: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    network: Mapped[AgentNetwork] = relationship("AgentNetwork", back_populates="nodes", foreign_keys=[network_id])
    # Optional: relationship to referenced child network (no back_populates to avoid cycles)
    child_network: Mapped[Optional[AgentNetwork]] = relationship("AgentNetwork", foreign_keys=[child_network_id])

    __table_args__ = (
        UniqueConstraint("network_id", "node_key", name="uq_network_node_key"),
        Index("ix_node_network", "network_id"),
    )


class AgentNetworkEdge(Base):
    __tablename__ = "agent_network_edge"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    network_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_network.id", ondelete="CASCADE"), nullable=False)
    source_node_key: Mapped[str] = mapped_column(String(64), nullable=False)
    target_node_key: Mapped[str] = mapped_column(String(64), nullable=False)
    condition: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    network: Mapped[AgentNetwork] = relationship("AgentNetwork", back_populates="edges")

    __table_args__ = (
        Index("ix_edge_network", "network_id"),
    )


class AgentNetworkInterface(Base):
    __tablename__ = "agent_network_interface"

    network_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_network.id", ondelete="CASCADE"), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    inputs_schema: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    outputs_schema: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    streaming: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    capabilities: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    network: Mapped[AgentNetwork] = relationship("AgentNetwork", back_populates="interface", foreign_keys=[network_id])


class AgentNetworkDependency(Base):
    __tablename__ = "agent_network_dependency"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    parent_network_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_network.id", ondelete="CASCADE"), nullable=False)
    child_network_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_network.id", ondelete="RESTRICT"), nullable=False)
    child_version_range: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("ix_dependency_parent", "parent_network_id"),
        Index("ix_dependency_child", "child_network_id"),
        UniqueConstraint("parent_network_id", "child_network_id", name="uq_network_dependency_pair"),
    )


class AgentNetworkRun(Base):
    __tablename__ = "agent_network_run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    network_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_network.id", ondelete="SET NULL"), nullable=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # queued | running | completed | failed | cancelled

    input_json: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    output_json: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    events_json: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    error_json: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    checkpoint: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


