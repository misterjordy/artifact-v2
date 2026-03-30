"""Pydantic input/output models for facts."""

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FactCreate(BaseModel):
    node_uid: UUID
    sentence: str = Field(min_length=10, max_length=2000)
    metadata_tags: list[str] = []
    source_reference: dict[str, Any] | None = None
    effective_date: str | None = None
    classification: str = "UNCLASSIFIED"


class FactUpdate(BaseModel):
    sentence: str = Field(min_length=10, max_length=2000)
    metadata_tags: list[str] = []
    source_reference: dict[str, Any] | None = None
    effective_date: str | None = None
    classification: str = "UNCLASSIFIED"
    change_summary: str | None = None


class VersionOut(BaseModel):
    version_uid: UUID
    fact_uid: UUID
    state: str
    display_sentence: str
    metadata_tags: list[str] = []
    source_reference: dict[str, Any] | None = None
    effective_date: str | None = None
    classification: str = "UNCLASSIFIED"
    change_summary: str | None = None
    supersedes_version_uid: UUID | None = None
    created_by_uid: UUID | None = None
    created_at: datetime
    published_at: datetime | None = None
    signed_at: datetime | None = None

    class Config:
        from_attributes = True


class FactOut(BaseModel):
    fact_uid: UUID
    node_uid: UUID
    current_published_version_uid: UUID | None = None
    current_signed_version_uid: UUID | None = None
    is_retired: bool
    created_at: datetime
    created_by_uid: UUID | None = None
    retired_at: datetime | None = None
    retired_by_uid: UUID | None = None

    class Config:
        from_attributes = True


class FactWithVersionOut(FactOut):
    current_version: VersionOut | None = None


class FactRetireRequest(BaseModel):
    pass


class FactMoveRequest(BaseModel):
    target_node_uid: UUID


class BulkRetireRequest(BaseModel):
    fact_uids: list[UUID]


class BulkMoveRequest(BaseModel):
    fact_uids: list[UUID]
    target_node_uid: UUID


# ── Fact History & Comments ──


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    comment_type: Literal["comment", "challenge", "resolution"] = "comment"
    parent_comment_uid: UUID | None = None
    proposed_sentence: str | None = Field(None, min_length=10, max_length=2000)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    comment_uid: UUID
    version_uid: UUID
    parent_comment_uid: UUID | None = None
    comment_type: str
    body: str
    created_by: dict[str, Any]
    created_at: datetime
    proposed_sentence: str | None = None
    resolution_state: str | None = None
    resolution_note: str | None = None
    resolved_at: datetime | None = None


class EventSummaryOut(BaseModel):
    event_uid: UUID
    event_type: str
    actor: dict[str, Any]
    occurred_at: datetime
    note: str | None = None


class MoveEventOut(BaseModel):
    event_uid: UUID
    event_type: str
    actor: dict[str, Any]
    occurred_at: datetime
    source_node_uid: str | None = None
    target_node_uid: str | None = None
    comment: str | None = None
    correlation_id: str | None = None
    note: str | None = None


class VersionHistoryOut(BaseModel):
    version_uid: UUID
    state: str
    display_sentence: str
    change_summary: str | None = None
    created_by: dict[str, Any]
    created_at: datetime
    published_at: datetime | None = None
    signed_at: datetime | None = None
    effective_date: str | None = None
    classification: str | None = None
    is_current_published: bool
    is_current_signed: bool
    comments: list[CommentOut] = []
    events: list[EventSummaryOut] = []


class FactHistoryOut(BaseModel):
    fact_uid: UUID
    node_uid: UUID
    current_sentence: str
    is_retired: bool
    versions: list[VersionHistoryOut] = []
    move_events: list[MoveEventOut] = []
