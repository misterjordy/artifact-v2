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


# ── Session-based chat schemas ───────────────────────────────────────


class CreateChatSession(BaseModel):
    program_node_uid: uuid.UUID
    constraint_node_uids: list[uuid.UUID] | None = None
    mode: str = Field(default="efficient", pattern="^(smart|efficient)$")
    fact_filter: str = Field(default="published", pattern="^(published|signed)$")


class ChatSessionOut(BaseModel):
    chat_uid: uuid.UUID
    program_name: str
    constraint_names: list[str]
    mode: str
    fact_filter: str
    message_count: int
    total_input_tokens: int
    total_output_tokens: int
    created_at: datetime
    last_message_at: datetime | None


class SendMessage(BaseModel):
    content: str = Field(..., min_length=1, max_length=10_000)


class ChatMessageOut(BaseModel):
    message_uid: uuid.UUID
    role: str
    content: str
    input_tokens: int
    output_tokens: int
    facts_loaded: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenEstimate(BaseModel):
    fact_count: int
    estimated_tokens: int
    warning: bool
