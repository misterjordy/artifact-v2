"""Acronym CRUD and row-level locking."""

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Conflict, NotFound
from artiFACT.kernel.models import FcAcronym, FcUser

log = structlog.get_logger()

LOCK_TIMEOUT_MINUTES = 5


# ── Locking ──


async def acquire_lock(
    db: AsyncSession,
    acronym_uid: UUID,
    user: FcUser,
) -> bool:
    """Acquire edit lock. Returns True if acquired, False if held by another user."""
    row = await db.get(FcAcronym, acronym_uid)
    if not row:
        raise NotFound("Acronym not found", code="ACRONYM_NOT_FOUND")

    now = datetime.now(timezone.utc)

    if (
        row.locked_by_uid
        and row.locked_by_uid != user.user_uid
        and row.locked_at
        and (now - row.locked_at).total_seconds() < LOCK_TIMEOUT_MINUTES * 60
    ):
        return False

    row.locked_by_uid = user.user_uid
    row.locked_at = now
    await db.flush()
    return True


async def release_lock(
    db: AsyncSession,
    acronym_uid: UUID,
    user: FcUser,
) -> None:
    """Release edit lock. Only the lock holder can release."""
    row = await db.get(FcAcronym, acronym_uid)
    if not row:
        raise NotFound("Acronym not found", code="ACRONYM_NOT_FOUND")
    if row.locked_by_uid == user.user_uid:
        row.locked_by_uid = None
        row.locked_at = None
        await db.flush()


async def check_lock(
    db: AsyncSession,
    acronym_uid: UUID,
    user: FcUser,
) -> None:
    """Raise Conflict if row is locked by another user."""
    row = await db.get(FcAcronym, acronym_uid)
    if not row:
        raise NotFound("Acronym not found", code="ACRONYM_NOT_FOUND")
    now = datetime.now(timezone.utc)
    if (
        row.locked_by_uid
        and row.locked_by_uid != user.user_uid
        and row.locked_at
        and (now - row.locked_at).total_seconds() < LOCK_TIMEOUT_MINUTES * 60
    ):
        raise Conflict(
            "This item is being edited by another user. Try again shortly.",
            code="ROW_LOCKED",
        )


# ── CRUD ──


async def list_acronyms(
    db: AsyncSession,
    *,
    q: str = "",
    limit: int = 1000,
    offset: int = 0,
    unresolved_only: bool = False,
) -> tuple[list[FcAcronym], int]:
    """List acronyms with optional text filter and unresolved filter."""
    stmt = select(FcAcronym).order_by(FcAcronym.acronym, FcAcronym.spelled_out)

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            FcAcronym.acronym.ilike(pattern) | FcAcronym.spelled_out.ilike(pattern)
        )
    if unresolved_only:
        stmt = stmt.where(FcAcronym.spelled_out.is_(None))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.offset(offset).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total


async def create_acronym(
    db: AsyncSession,
    acronym: str,
    spelled_out: str | None,
    user: FcUser,
) -> FcAcronym:
    """Create a single acronym entry."""
    row = FcAcronym(
        acronym=acronym.strip(),
        spelled_out=spelled_out.strip() if spelled_out else None,
        created_by_uid=user.user_uid,
    )
    db.add(row)
    await db.flush()
    log.info("acronym.created", acronym=row.acronym, uid=str(row.acronym_uid))
    return row


async def create_acronyms_bulk(
    db: AsyncSession,
    items: list[dict[str, str | None]],
    user: FcUser,
) -> int:
    """Bulk create acronyms. Skips exact duplicates. Returns inserted count."""
    existing_result = await db.execute(
        select(FcAcronym.acronym, FcAcronym.spelled_out)
    )
    existing_set: set[tuple[str, str]] = {
        (r.acronym.strip().upper(), (r.spelled_out or "").strip().upper())
        for r in existing_result.all()
    }

    inserted = 0
    for item in items:
        acro = (item.get("acronym") or "").strip()[:50]
        expansion = (item.get("spelled_out") or "").strip()[:200]
        if not acro:
            continue

        key = (acro.upper(), expansion.upper())
        if key in existing_set:
            continue

        db.add(FcAcronym(
            acronym=acro,
            spelled_out=expansion if expansion else None,
            created_by_uid=user.user_uid,
        ))
        existing_set.add(key)
        inserted += 1

    await db.flush()
    return inserted


_UNSET = object()


async def update_acronym(
    db: AsyncSession,
    acronym_uid: UUID,
    user: FcUser,
    *,
    acronym: str | None = None,
    spelled_out: object = _UNSET,
) -> FcAcronym:
    """Update an acronym. Checks row lock first."""
    await check_lock(db, acronym_uid, user)

    row = await db.get(FcAcronym, acronym_uid)
    if not row:
        raise NotFound("Acronym not found", code="ACRONYM_NOT_FOUND")

    if acronym is not None:
        row.acronym = acronym.strip()
    if spelled_out is not _UNSET:
        val = str(spelled_out).strip() if spelled_out else None
        row.spelled_out = val
    row.updated_by_uid = user.user_uid

    await db.flush()
    return row


async def delete_acronyms_bulk(
    db: AsyncSession,
    uids: list[UUID],
    user: FcUser,
) -> int:
    """Delete multiple acronyms. Fails if any are locked by another user."""
    now = datetime.now(timezone.utc)
    rows: list[FcAcronym] = []
    for uid in uids:
        row = await db.get(FcAcronym, uid)
        if not row:
            continue
        if (
            row.locked_by_uid
            and row.locked_by_uid != user.user_uid
            and row.locked_at
            and (now - row.locked_at).total_seconds() < LOCK_TIMEOUT_MINUTES * 60
        ):
            raise Conflict(
                "One or more items are checked out by another user. "
                "Please refresh and try again.",
                code="ROW_LOCKED",
            )
        rows.append(row)

    for row in rows:
        await db.delete(row)
    await db.flush()
    return len(rows)


async def get_all_for_tooltips(
    db: AsyncSession,
) -> dict[str, list[str]]:
    """Return acronym → expansions dict for client-side tooltips. Excludes unresolved."""
    result = await db.execute(
        select(FcAcronym.acronym, FcAcronym.spelled_out)
        .where(FcAcronym.spelled_out.isnot(None))
        .order_by(FcAcronym.acronym)
    )

    acronym_dict: dict[str, list[str]] = {}
    for row in result.all():
        key = row.acronym.strip()
        if key not in acronym_dict:
            acronym_dict[key] = []
        acronym_dict[key].append(row.spelled_out.strip())
    return acronym_dict
