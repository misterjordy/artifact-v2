"""Pydantic models for AI chat endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    node_uid: uuid.UUID | None = None
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    content: str
    facts_loaded: int
    facts_total: int
    node_title: str | None = None
    flagged: bool = False


class ContextNode(BaseModel):
    node_uid: uuid.UUID
    title: str
    node_depth: int
    parent_node_uid: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class ContextOut(BaseModel):
    programs: list[ContextNode]
    topics: dict[str, list[ContextNode]]


class AIKeyIn(BaseModel):
    provider: str = Field(pattern="^(openai|anthropic|azure_openai|bedrock)$")
    api_key: str = Field(min_length=5, max_length=500)
    model_override: str | None = None


class AIKeyOut(BaseModel):
    key_uid: uuid.UUID
    provider: str
    key_prefix: str | None
    model_override: str | None
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


class AIStatusOut(BaseModel):
    has_key: bool
    keys: list[AIKeyOut]
