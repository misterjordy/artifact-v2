"""Pydantic models for move endpoints."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ProposeFactMove(BaseModel):
    fact_uid: UUID
    target_node_uid: UUID
    comment: str = Field(..., min_length=1, max_length=2000)
    auto_approve: bool = False


class ProposeNodeMove(BaseModel):
    node_uid: UUID
    target_parent_uid: UUID
    comment: str = Field(..., min_length=1, max_length=2000)
    auto_approve: bool = False


class RejectMoveRequest(BaseModel):
    note: str | None = Field(None, max_length=2000)


class MoveResultOut(BaseModel):
    status: str
    event_uid: str | None = None
    fact_count: int | None = None
    correlation_id: str | None = None
    moved_count: int | None = None
    rejected_count: int | None = None


class PendingMoveOut(BaseModel):
    event_uid: UUID
    entity_type: str
    entity_uid: UUID
    event_type: str
    payload: dict[str, Any]
    actor_uid: UUID | None = None
    occurred_at: datetime
    correlation_id: str | None = None
