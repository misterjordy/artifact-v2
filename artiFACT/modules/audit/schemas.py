"""Pydantic input/output models for audit."""

from datetime import datetime
from uuid import UUID

from typing import Any

from pydantic import BaseModel


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


class UndoResult(BaseModel):
    event_uid: UUID
    message: str
