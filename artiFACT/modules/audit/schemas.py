"""Pydantic input/output models for audit."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EventOut(BaseModel):
    event_uid: UUID
    entity_type: str
    entity_uid: UUID
    event_type: str
    payload: dict[str, Any] | None = None
    actor_uid: UUID | None = None
    note: str | None = None
    occurred_at: datetime
    reversible: bool

    class Config:
        from_attributes = True


# ── Undo schemas ──


class UndoActionLine(BaseModel):
    """A single line in the undo pane."""

    event_uid: UUID
    event_type: str
    description: str
    entity_detail: str
    context: dict[str, Any] | None = None
    occurred_at: datetime
    is_undoable: bool
    lock_reason: str | None = None
    is_bulk: bool = False
    bulk_count: int = 1
    bulk_event_uids: list[UUID] = []


class UndoActionsResponse(BaseModel):
    actions: list[UndoActionLine]
    total: int


class BulkUndoRequest(BaseModel):
    event_uids: list[UUID] = Field(..., min_length=1)


class UndoResponse(BaseModel):
    status: str
    detail: str = ""
    count: int = 1
    details: list[str] = []


# Keep for backward compat with existing tests
class UndoResult(BaseModel):
    event_uid: UUID
    message: str
