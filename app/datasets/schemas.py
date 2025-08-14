from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class DatasetBase(BaseModel):
    name: str = Field(..., max_length=128)
    category: Literal["sql", "vector", "blob", "other"]
    description: Optional[str] = Field(None, max_length=1024)
    tags: Optional[dict] = None
    is_enabled: Optional[bool] = True
    data_source_id: str
    config: Dict[str, Any]
    config_schema_version: Optional[str] = None


class DatasetCreate(DatasetBase):
    pass


class DatasetUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = Field(None, max_length=1024)
    tags: Optional[dict] = None
    is_enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    config_schema_version: Optional[str] = None


class DatasetResponse(BaseModel):
    id: str
    tenant_id: str
    owner_id: str
    name: str
    category: str
    description: Optional[str]
    tags: Optional[dict]
    is_enabled: bool
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str
    data_source_id: str
    config: Dict[str, Any]
    config_schema_version: Optional[str]

    class Config:
        from_attributes = True


# Operation Schemas

class SQLSelectRequest(BaseModel):
    columns: Optional[List[str]] = None
    where: Optional[str] = None  # parameterized expression, provider validates
    params: Optional[Dict[str, Any]] = None
    order_by: Optional[List[Dict[str, str]]] = None  # [{column, direction}]
    limit: Optional[int] = Field(default=None, ge=1)
    offset: Optional[int] = Field(default=0, ge=0)


class VectorQueryRequest(BaseModel):
    vector: List[float]
    top_k: int = Field(..., ge=1)
    filter: Optional[Dict[str, Any]] = None
    include_values: Optional[bool] = False
    include_metadata: Optional[bool] = True
    namespace: Optional[str] = None


class BlobGetRequest(BaseModel):
    range: Optional[Dict[str, Optional[int]]] = Field(None, description="{ start?: int, end?: int }")


class BlobPresignRequest(BaseModel):
    ttl_s: Optional[int] = Field(None, ge=1)


