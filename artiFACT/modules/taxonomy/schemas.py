"""Input/output Pydantic models for taxonomy."""

import uuid

from pydantic import BaseModel, Field

from artiFACT.kernel.schemas import NodeOut


class NodeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    parent_node_uid: uuid.UUID | None = None
    sort_order: int = 0


class NodeUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    sort_order: int | None = None


class NodeMove(BaseModel):
    new_parent_uid: uuid.UUID | None = None


class NodeDetail(NodeOut):
    breadcrumb: list[NodeOut] = []
    children: list[NodeOut] = []


class TreeOut(BaseModel):
    flat: list[NodeOut]
    nested: list[dict]
