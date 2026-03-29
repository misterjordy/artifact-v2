"""Shared Pydantic models (UserOut, NodeOut, etc.)."""

import uuid
from datetime import datetime

from pydantic import BaseModel


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
    created_at: datetime

    model_config = {"from_attributes": True}
