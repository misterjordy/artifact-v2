"""Pydantic models for search results and acronym entries."""

import uuid

from pydantic import BaseModel


class BreadcrumbEntry(BaseModel):
    node_uid: uuid.UUID
    title: str
    slug: str


class SearchResult(BaseModel):
    version_uid: uuid.UUID
    fact_uid: uuid.UUID
    node_uid: uuid.UUID
    display_sentence: str
    state: str
    rank: float
    breadcrumb: list[BreadcrumbEntry]

    model_config = {"from_attributes": True}


class AcronymEntry(BaseModel):
    acronym: str
    count: int
