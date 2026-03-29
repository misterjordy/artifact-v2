"""Pydantic input/output models for signing endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SignRequest(BaseModel):
    note: str | None = Field(None, max_length=2000)
    expires_at: datetime | None = None


class SignatureOut(BaseModel):
    signature_uid: UUID
    node_uid: UUID
    signed_by_uid: UUID
    signed_at: datetime
    fact_count: int
    note: str | None = None
    expires_at: datetime | None = None

    class Config:
        from_attributes = True


class SignPaneItem(BaseModel):
    node_uid: UUID
    node_title: str
    unsigned_count: int
