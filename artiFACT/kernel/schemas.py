"""Shared Pydantic models (UserOut, NodeOut, etc.)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class UserOut(BaseModel):
    user_uid: uuid.UUID
    cac_dn: str
    edipi: str | None = None
    display_name: str
    email: str | None = None
    global_role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class NodeOut(BaseModel):
    node_uid: uuid.UUID
    parent_node_uid: uuid.UUID | None = None
    title: str
    slug: str
    node_depth: int
    sort_order: int
    is_archived: bool
    is_program: bool = False
    program_description: str | None = None
    program_description_source: str | None = None
    created_at: datetime

    @field_validator("is_program", mode="before")
    @classmethod
    def _coerce_is_program(cls, v: bool | None) -> bool:
        return bool(v)

    model_config = {"from_attributes": True}
