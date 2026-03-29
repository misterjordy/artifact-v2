"""Admin-only API endpoints: dashboard, user management, config, health, cache, snapshots."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.db import get_db
from artiFACT.kernel.events import publish
from artiFACT.kernel.exceptions import Forbidden, NotFound
from artiFACT.kernel.models import FcUser
from artiFACT.modules.admin.cache_manager import flush_all, flush_by_pattern, get_cache_stats
from artiFACT.modules.admin.config_manager import list_config, upsert_config
from artiFACT.modules.admin.dashboard import get_dashboard
from artiFACT.modules.admin.module_health import check_db, check_redis, check_s3, get_module_health
from artiFACT.modules.admin.schemas import (
    CacheStatsOut,
    ConfigOut,
    ConfigUpdate,
    DashboardMetrics,
    HealthCheckOut,
    RoleUpdate,
    SnapshotOut,
    UserListOut,
    UserListResponse,
)
from artiFACT.modules.admin.snapshot_manager import trigger_snapshot

VALID_ROLES = {"admin", "signatory", "approver", "subapprover", "contributor", "viewer"}

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _require_admin(user: FcUser) -> None:
    """Raise 403 if user is not an admin."""
    if user.global_role != "admin":
        raise Forbidden("Admin access required", code="ADMIN_REQUIRED")


# ── Dashboard ──


@router.get("/dashboard")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> DashboardMetrics:
    _require_admin(user)
    metrics = await get_dashboard(db)
    return DashboardMetrics(**metrics)


# ── User management ──


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
    q: str | None = Query(None, description="Search by display_name or cac_dn"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> UserListResponse:
    _require_admin(user)
    stmt = select(FcUser)
    count_stmt = select(func.count(FcUser.user_uid))

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(FcUser.display_name.ilike(pattern) | FcUser.cac_dn.ilike(pattern))
        count_stmt = count_stmt.where(
            FcUser.display_name.ilike(pattern) | FcUser.cac_dn.ilike(pattern)
        )

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.order_by(FcUser.display_name).offset(offset).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    return UserListResponse(
        data=[UserListOut.model_validate(r) for r in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.put("/users/{user_uid}/role")
async def change_user_role(
    user_uid: uuid.UUID,
    body: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> UserListOut:
    _require_admin(user)
    if body.global_role not in VALID_ROLES:
        raise Forbidden(f"Invalid role: {body.global_role}")

    target = await db.get(FcUser, user_uid)
    if not target:
        raise NotFound("User not found", code="USER_NOT_FOUND")

    old_role = target.global_role
    target.global_role = body.global_role
    await db.flush()

    await publish(
        "admin.role_changed",
        {
            "user_uid": str(user_uid),
            "old_role": old_role,
            "new_role": body.global_role,
            "actor_uid": str(user.user_uid),
        },
    )

    return UserListOut.model_validate(target)


@router.post("/users/{user_uid}/deactivate")
async def deactivate_user(
    user_uid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> UserListOut:
    _require_admin(user)
    target = await db.get(FcUser, user_uid)
    if not target:
        raise NotFound("User not found", code="USER_NOT_FOUND")

    target.is_active = False
    await db.flush()

    await publish(
        "admin.user_deactivated",
        {
            "user_uid": str(user_uid),
            "actor_uid": str(user.user_uid),
        },
    )

    return UserListOut.model_validate(target)


@router.post("/users/{user_uid}/reactivate")
async def reactivate_user(
    user_uid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> UserListOut:
    _require_admin(user)
    target = await db.get(FcUser, user_uid)
    if not target:
        raise NotFound("User not found", code="USER_NOT_FOUND")

    target.is_active = True
    await db.flush()

    await publish(
        "admin.user_reactivated",
        {
            "user_uid": str(user_uid),
            "actor_uid": str(user.user_uid),
        },
    )

    return UserListOut.model_validate(target)


# ── Module health ──


@router.get("/modules")
async def modules_health(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    _require_admin(user)
    return await get_module_health(db)


# ── Feature flags / config ──


@router.get("/config")
async def get_all_config(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> list[ConfigOut]:
    _require_admin(user)
    rows = await list_config(db)
    return [ConfigOut.model_validate(r) for r in rows]


@router.post("/config/{key}")
async def update_config(
    key: str,
    body: ConfigUpdate,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> ConfigOut:
    _require_admin(user)
    row = await upsert_config(db, key, body.value, user.user_uid)
    return ConfigOut.model_validate(row)


# ── Snapshots ──


@router.post("/snapshot")
async def create_snapshot(
    user: FcUser = Depends(get_current_user),
) -> SnapshotOut:
    _require_admin(user)
    trigger_snapshot.delay(str(user.user_uid))
    return SnapshotOut(
        filename="pending",
        size=0,
        status="queued",
    )


# ── Cache ──


@router.get("/cache/stats")
async def cache_stats(
    user: FcUser = Depends(get_current_user),
) -> CacheStatsOut:
    _require_admin(user)
    stats = await get_cache_stats()
    return CacheStatsOut(**stats)


@router.post("/cache/flush")
async def flush_cache(
    user: FcUser = Depends(get_current_user),
    category: str | None = Query(None, description="Flush pattern: permissions, badges, or all"),
) -> dict[str, Any]:
    _require_admin(user)

    if category == "permissions":
        count = await flush_by_pattern("permissions:*")
    elif category == "badges":
        count = await flush_by_pattern("badge:*")
    elif category is None or category == "all":
        count = await flush_all()
    else:
        count = await flush_by_pattern(f"{category}:*")

    await publish(
        "admin.cache_flushed",
        {
            "category": category or "all",
            "keys_flushed": count,
            "actor_uid": str(user.user_uid),
        },
    )

    return {"flushed": count, "category": category or "all"}


# ── Detailed health ──


@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> HealthCheckOut:
    _require_admin(user)
    db_ok = await check_db(db)
    redis_ok = await check_redis()
    s3_ok = check_s3()
    module_list = await get_module_health(db)

    return HealthCheckOut(
        db=db_ok,
        redis=redis_ok,
        s3=s3_ok,
        modules=[
            {"module": m["module"], "db": m["db"], "redis": m["redis"], "s3": m["s3"]}
            for m in module_list
        ],
    )
