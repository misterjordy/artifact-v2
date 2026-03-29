"""Pydantic input/output models for facts."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


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
