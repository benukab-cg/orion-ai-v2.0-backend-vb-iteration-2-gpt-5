from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


REDACTED = "__REDACTED__"


class AIModelBase(BaseModel):
    name: str = Field(..., max_length=128)
    type: str = Field(..., description="Connector type slug, e.g., 'llm.openai'")
    category: str = Field(..., description="One of: llm|embedding")
    description: Optional[str] = Field(None, max_length=1024)
    tags: Optional[dict] = None
    is_enabled: Optional[bool] = True
    config: Dict[str, Any]
    config_schema_version: Optional[str] = None


class AIModelCreate(AIModelBase):
    pass


class AIModelUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = Field(None, max_length=1024)
    tags: Optional[dict] = None
    is_enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    config_schema_version: Optional[str] = None


class AIModelResponse(BaseModel):
    id: str
    tenant_id: str
    owner_id: str
    name: str
    type: str
    category: str
    description: Optional[str]
    tags: Optional[dict]
    is_enabled: bool
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str
    config: Dict[str, Any]
    config_schema_version: Optional[str]

    class Config:
        from_attributes = True


class TypesListItem(BaseModel):
    type: str
    display_name: str
    category: str
    version: str
    json_schema: dict
    source: str



