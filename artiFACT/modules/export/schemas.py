"""Pydantic input/output models for export module."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FactsheetRequest(BaseModel):
    node_uids: list[uuid.UUID] = Field(..., min_length=1)
    format: str = Field("json", pattern="^(txt|json|ndjson|csv)$")
    state_filter: list[str] = Field(default=["published"])


class TemplateSection(BaseModel):
    key: str
    title: str
    prompt: str
    guidance: str = ""


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    abbreviation: str = Field(..., min_length=1, max_length=20)
    description: str | None = None
    sections: list[TemplateSection] = Field(..., min_length=1)


class TemplateUpdate(BaseModel):
    name: str | None = None
    abbreviation: str | None = None
    description: str | None = None
    sections: list[TemplateSection] | None = None
    is_active: bool | None = None


class TemplateOut(BaseModel):
    template_uid: uuid.UUID
    name: str
    abbreviation: str
    description: str | None
    sections: list[dict]
    is_active: bool
    created_by_uid: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentRequest(BaseModel):
    node_uids: list[uuid.UUID] = Field(..., min_length=1)
    template_uid: uuid.UUID


class DocumentOut(BaseModel):
    session_uid: uuid.UUID
    status: str


class DownloadURL(BaseModel):
    url: str
    expires_in: int = 3600


class ProgressEvent(BaseModel):
    session_uid: uuid.UUID
    stage: str
    percent: float
    download_url: str | None = None


class ViewsRequest(BaseModel):
    node_uids: list[uuid.UUID] = Field(..., min_length=1)
    template_uid: uuid.UUID


class SectionAssignment(BaseModel):
    section_key: str
    section_title: str
    facts: list[dict]


class ViewsOut(BaseModel):
    template_uid: uuid.UUID
    template_name: str
    assignments: list[SectionAssignment]


class SyncChangeOut(BaseModel):
    seq: int
    occurred_at: datetime
    change_type: str
    entity_type: str
    entity_uid: uuid.UUID
    snapshot: dict


class DeltaFeedOut(BaseModel):
    changes: list[SyncChangeOut]
    cursor: int
    has_more: bool


class FullDumpOut(BaseModel):
    exported_at: datetime
    schema_version: str = "2.0"
    nodes: list[dict]
    facts: list[dict]
    versions: list[dict]
    signatures: list[dict]
    users: list[dict]
    templates: list[dict]
    events: list[dict]
    cursor: int
