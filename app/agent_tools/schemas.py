from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, conint, field_validator


class ResourceBinding(BaseModel):
    type: Literal["dataset", "ai_model", "datasource"]
    id: UUID
    role: str = Field(..., max_length=64)


class ToolBindings(BaseModel):
    resources: list[ResourceBinding] = Field(default_factory=list)


class SQLSelectConfig(BaseModel):
    default_columns: Optional[list[str]] = None
    max_rows: conint(ge=1, le=5000) = 500
    query_timeout_s: conint(ge=1, le=60) = 15
    allowed_predicates: Optional[list[str]] = None


class VectorSimilaritySearchConfig(BaseModel):
    top_k: conint(ge=1, le=1000) = 10
    include_metadata: bool = True
    include_values: bool = False
    namespace: Optional[str] = None
    allowed_metadata_fields: Optional[list[str]] = None
    embed_text_max_chars: conint(ge=1, le=100000) = 8000


class AgentToolBase(BaseModel):
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    tags: Optional[dict] = None
    kind: Literal["sql.select", "vector.similarity_search"]
    provider: Optional[str] = None
    is_enabled: Optional[bool] = True
    bindings: Optional[ToolBindings] = None


class AgentToolCreate(AgentToolBase):
    config: dict
    config_schema_version: Optional[str] = None


class AgentToolUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = None
    tags: Optional[dict] = None
    is_enabled: Optional[bool] = None
    bindings: Optional[ToolBindings] = None
    config: Optional[dict] = None
    config_schema_version: Optional[str] = None


class AgentToolResponse(BaseModel):
    id: UUID
    tenant_id: str
    owner_id: str
    name: str
    kind: str
    provider: Optional[str]
    description: Optional[str]
    tags: Optional[dict]
    is_enabled: bool
    bindings: Optional[ToolBindings]
    created_at: Any
    updated_at: Any
    created_by: str
    updated_by: str
    config: dict
    config_schema_version: Optional[str]


class InvokeSQLSelectRequest(BaseModel):
    columns: Optional[list[str]] = None
    where: Optional[dict] = None
    params: Optional[dict] = None
    order_by: Optional[list[str]] = None
    limit: Optional[int] = None
    offset: Optional[int] = None


class InvokeVectorSimilaritySearchRequest(BaseModel):
    vector: Optional[list[float]] = None
    text: Optional[str] = None
    top_k: Optional[int] = None
    filter: Optional[dict] = None
    include_values: Optional[bool] = None
    include_metadata: Optional[bool] = None
    namespace: Optional[str] = None


class AgentToolInvokeRequest(BaseModel):
    # Polymorphic payload; validated again by adapter based on kind
    payload: dict


