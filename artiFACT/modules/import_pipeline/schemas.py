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
