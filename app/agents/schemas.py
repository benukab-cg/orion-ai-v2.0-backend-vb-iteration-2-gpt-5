from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AgentBase(BaseModel):
    name: str = Field(..., max_length=128)
    description: Optional[str] = Field(None, max_length=1024)
    tags: Optional[dict] = None
    type: str = Field("langgraph.single")
    ai_model_id: str
    is_enabled: Optional[bool] = True
    bindings: Optional[dict] = None  # { tools: [UUID, ...] }
    config: Dict[str, Any]
    config_schema_version: Optional[str] = None


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = Field(None, max_length=1024)
    tags: Optional[dict] = None
    ai_model_id: Optional[str] = None
    is_enabled: Optional[bool] = None
    bindings: Optional[dict] = None
    config: Optional[Dict[str, Any]] = None
    config_schema_version: Optional[str] = None


class AgentResponse(BaseModel):
    id: str
    tenant_id: str
    owner_id: str
    name: str
    type: str
    description: Optional[str]
    tags: Optional[dict]
    ai_model_id: str
    is_enabled: bool
    bindings: Optional[dict]
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str
    config: Dict[str, Any]
    config_schema_version: Optional[str]

    class Config:
        from_attributes = True


class AgentInvokeRequest(BaseModel):
    input: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None
    messages: Optional[list[Dict[str, Any]]] = None
    tool_overrides: Optional[Dict[str, Any]] = None
    llm_overrides: Optional[Dict[str, Any]] = None
    stream: Optional[bool] = None



