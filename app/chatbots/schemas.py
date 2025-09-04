from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ChatbotBase(BaseModel):
    name: str = Field(..., max_length=128)
    slug: str = Field(..., max_length=128)
    description: Optional[str] = Field(None, max_length=1024)
    visibility: Optional[str] = Field(None)
    is_enabled: Optional[bool] = True
    agent_network_id: str
    agent_network_version: str


class ChatbotCreate(ChatbotBase):
    pass


class ChatbotUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    slug: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = Field(None, max_length=1024)
    visibility: Optional[str] = Field(None)
    is_enabled: Optional[bool] = None
    agent_network_id: Optional[str] = None
    agent_network_version: Optional[str] = None


class ChatbotResponse(BaseModel):
    id: str
    tenant_id: str
    owner_id: str
    name: str
    slug: str
    description: Optional[str]
    visibility: Optional[str]
    is_enabled: bool
    agent_network_id: str
    agent_network_version: str
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str

    class Config:
        from_attributes = True


class ChatbotInvokeRequest(BaseModel):
    input: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None
    messages: Optional[list[Dict[str, Any]]] = None
    stream: Optional[bool] = None


class ChatThreadCreate(BaseModel):
    title: Optional[str] = None
    tags: Optional[dict] = None


class ChatThreadUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[dict] = None


class ChatThreadResponse(BaseModel):
    id: str
    chatbot_id: str
    user_id: str
    title: Optional[str]
    status: str
    tags: Optional[dict]
    last_message_at: Optional[datetime]
    token_usage: Optional[Dict[str, Any]]
    last_run_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatMessageCreate(BaseModel):
    content: Dict[str, Any]


class ChatMessageResponse(BaseModel):
    id: str
    thread_id: str
    role: str
    content_json: Dict[str, Any]
    citations_json: Optional[Dict[str, Any]]
    run_id: Optional[str]
    token_counts_json: Optional[Dict[str, Any]]
    latency_ms: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


