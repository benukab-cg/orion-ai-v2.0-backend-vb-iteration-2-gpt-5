from __future__ import annotations

from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


NetworkType = Literal["standalone", "supervised", "swarm", "custom"]
NetworkStatus = Literal["draft", "active", "deprecated"]


class AgentNetworkNodeSpec(BaseModel):
    node_key: str = Field(min_length=1, max_length=64)
    role: Optional[str] = Field(default=None, max_length=32)
    agent_id: Optional[UUID] = None
    child_network_id: Optional[UUID] = None
    child_network_version: Optional[str] = None
    config: Optional[dict] = None

    @field_validator("child_network_version")
    @classmethod
    def _trim(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if isinstance(v, str) else v


class AgentNetworkEdgeSpec(BaseModel):
    source_node_key: str
    target_node_key: str
    condition: Optional[str] = None


class AgentNetworkSpec(BaseModel):
    type: NetworkType
    nodes: list[AgentNetworkNodeSpec]
    edges: list[AgentNetworkEdgeSpec] = Field(default_factory=list)
    interface: Optional[dict] = None  # optional embedded interface override
    swarm: Optional[dict] = None  # { default_active_agent?: str, handoff_policy?: 'allow_all'|'edges' }


class AgentNetworkCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=128)
    type: NetworkType
    description: Optional[str] = None
    tags: Optional[dict] = None
    version: str = Field(min_length=1, max_length=32)
    status: NetworkStatus = "draft"
    spec: AgentNetworkSpec
    is_enabled: bool = True


class AgentNetworkUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[dict] = None
    status: Optional[NetworkStatus] = None
    spec: Optional[AgentNetworkSpec] = None
    is_enabled: Optional[bool] = None


class AgentNetworkResponse(BaseModel):
    id: UUID
    tenant_id: str
    owner_id: str
    name: str
    slug: str
    type: NetworkType
    description: Optional[str]
    tags: Optional[dict]
    version: str
    status: NetworkStatus
    is_enabled: bool
    created_at: str
    updated_at: str
    spec: AgentNetworkSpec


class AgentNetworkInterfaceDescriptor(BaseModel):
    version: str
    inputs_schema: dict
    outputs_schema: dict
    streaming: bool = False
    capabilities: Optional[dict] = None


class AgentNetworkInvokeRequest(BaseModel):
    input: dict | str | None = None
    variables: Optional[dict] = None
    runtime_overrides: Optional[dict] = None



