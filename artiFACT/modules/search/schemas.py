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


class GroupedSearchResult(BaseModel):
    fact_uid: str
    version_uid: str
    display_sentence: str
    state: str
    node_uid: str
    score: float
    breadcrumb: str


class ProgramGroup(BaseModel):
    program_uid: str
    program_title: str
    results: list[GroupedSearchResult]


class GroupedSearchResponse(BaseModel):
    programs: list[ProgramGroup]
    total: int


class AcronymEntry(BaseModel):
    acronym: str
    count: int
