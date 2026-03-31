"""Pydantic input/output models for import pipeline."""

from datetime import date, datetime
from uuid import UUID

from typing import Any

from pydantic import BaseModel, Field


class UploadRequest(BaseModel):
    program_node_uid: UUID
    effective_date: date
    granularity: str = "standard"


class SessionOut(BaseModel):
    session_uid: UUID
    program_node_uid: UUID
    source_filename: str
    source_hash: str
    granularity: str
    effective_date: date
    status: str
    error_message: str | None = None
    input_type: str = "document"
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class StagedFact(BaseModel):
    index: int
    sentence: str
    metadata_tags: list[str] = []
    source_reference: dict[str, Any] | None = None
    duplicate_of: str | None = None
    similarity: float | None = None
    accepted: bool = True


class StagedFactsOut(BaseModel):
    session_uid: UUID
    facts: list[StagedFact]
    total: int


class ProposeRequest(BaseModel):
    accepted_indices: list[int] = Field(default_factory=list)


class ProposeOut(BaseModel):
    created_count: int
    session_uid: UUID


class RecommendLocationRequest(BaseModel):
    sentences: list[str]
    program_node_uid: UUID


class RecommendLocationOut(BaseModel):
    recommendations: list[dict[str, Any]]


# --- New schemas for import pipeline v2 ---


class PasteImportRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=100_000)
    program_node_uid: UUID
    effective_date: date
    granularity: str = Field(default="standard")
    constraint_node_uids: list[UUID] | None = None


class StagedFactOut(BaseModel):
    staged_fact_uid: UUID
    display_sentence: str
    suggested_node_uid: UUID | None
    node_confidence: float | None
    node_alternatives: list[dict[str, Any]]
    status: str
    duplicate_of_uid: UUID | None
    similarity_score: float | None
    conflict_with_uid: UUID | None
    conflict_reason: str | None
    resolution: str | None
    source_chunk_index: int | None

    model_config = {"from_attributes": True}


class StagedFactUpdate(BaseModel):
    suggested_node_uid: UUID | None = None
    display_sentence: str | None = None
    status: str | None = None
    resolution: str | None = None
