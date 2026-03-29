"""Pydantic schemas for admin module."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class DashboardMetrics(BaseModel):
    users: dict
    facts: dict
    queue: dict
    system: dict


class UserListOut(BaseModel):
    user_uid: uuid.UUID
    cac_dn: str
    display_name: str
    email: str | None = None
    global_role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    data: list[UserListOut]
    total: int
    offset: int
    limit: int


class RoleUpdate(BaseModel):
    global_role: str


class ConfigOut(BaseModel):
    key: str
    value: dict
    updated_at: datetime
    updated_by_uid: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class ConfigUpdate(BaseModel):
    value: dict


class ModuleHealthOut(BaseModel):
    module: str
    db: bool
    redis: bool
    s3: bool


class CacheStatsOut(BaseModel):
    used_memory_human: str
    connected_clients: int
    keyspace_hits: int
    keyspace_misses: int
    total_keys: int


class SnapshotOut(BaseModel):
    filename: str
    size: int
    status: str


class HealthCheckOut(BaseModel):
    db: bool
    redis: bool
    s3: bool
    modules: list[ModuleHealthOut]
