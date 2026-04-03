"""Pydantic schemas for acronym endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AcronymCreate(BaseModel):
    acronym: str = Field(..., min_length=1, max_length=50)
    spelled_out: str | None = Field(None, max_length=500)


class AcronymBulkCreate(BaseModel):
    items: list[AcronymCreate] = Field(..., max_length=5000)


class AcronymUpdate(BaseModel):
    acronym: str | None = Field(None, max_length=50)
    spelled_out: str | None = Field(None, max_length=500)


class AcronymBulkDelete(BaseModel):
    acronym_uids: list[UUID]


class AcronymOut(BaseModel):
    acronym_uid: UUID
    acronym: str
    spelled_out: str | None
    created_at: datetime
    updated_at: datetime
    locked_by_uid: UUID | None
    locked_at: datetime | None

    model_config = {"from_attributes": True}
