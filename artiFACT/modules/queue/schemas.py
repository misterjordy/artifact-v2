"""Pydantic input/output models for queue endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProposalOut(BaseModel):
    version_uid: UUID
    fact_uid: UUID
    node_uid: UUID
    node_title: str
    display_sentence: str
    state: str
    classification: str = "UNCLASSIFIED"
    created_by_uid: UUID | None = None
    created_by_name: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class MoveProposalOut(BaseModel):
    event_uid: UUID
    fact_uid: UUID
    display_sentence: str
    source_node_uid: UUID
    source_node_title: str
    target_node_uid: UUID
    target_node_title: str
    actor_uid: UUID | None = None
    actor_name: str | None = None
    occurred_at: datetime

    class Config:
        from_attributes = True


class ApproveRequest(BaseModel):
    note: str | None = None


class RejectRequest(BaseModel):
    note: str | None = Field(None, max_length=2000)


class ReviseRequest(BaseModel):
    revised_sentence: str = Field(min_length=10, max_length=2000)
    note: str | None = None


class BadgeCountOut(BaseModel):
    proposals: int = 0
    moves: int = 0
    total: int = 0
