"""Acronym API endpoints: CRUD, locking, corpus scan, AI lookup, tooltip cache, CSV export."""

import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.db import get_db
from artiFACT.kernel.exceptions import Forbidden
from artiFACT.kernel.models import FcUser
from artiFACT.modules.acronyms.lookup import lookup_acronym_expansion
from artiFACT.modules.acronyms.scanner import scan_and_insert
from artiFACT.modules.acronyms.schemas import (
    AcronymBulkCreate,
    AcronymBulkDelete,
    AcronymCreate,
    AcronymOut,
    AcronymUpdate,
)
from artiFACT.modules.acronyms.seeder import seed_acronyms
from artiFACT.modules.acronyms.service import (
    acquire_lock,
    create_acronym,
    create_acronyms_bulk,
    delete_acronyms_bulk,
    get_all_for_tooltips,
    list_acronyms,
    release_lock,
    update_acronym,
)

router = APIRouter(prefix="/api/v1", tags=["acronyms"])


# ── List / Filter ──


@router.get("/acronyms")
async def list_acronyms_endpoint(
    q: str = Query("", max_length=200),
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    unresolved_only: bool = Query(False),
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all acronyms with optional text filter and unresolved filter."""
    rows, total = await list_acronyms(
        db, q=q, limit=limit, offset=offset, unresolved_only=unresolved_only,
    )
    return {
        "data": [AcronymOut.model_validate(r).model_dump(mode="json") for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


# ── Tooltip cache ──


@router.get("/acronyms/all")
async def get_all_acronyms_for_tooltips(
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Lightweight grouped dict for client-side tooltips. Excludes unresolved."""
    acronym_dict = await get_all_for_tooltips(db)
    return {"data": {"acronyms": acronym_dict}}


# ── CSV export ──


@router.get("/acronyms/export")
async def export_acronyms_csv(
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Download all acronyms as CSV."""
    rows, _ = await list_acronyms(db, limit=100_000)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Acronym", "Spelled Out"])
    for row in rows:
        writer.writerow([row.acronym, row.spelled_out or ""])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=acronyms.csv"},
    )


# ── Create ──


@router.post("/acronyms")
async def create_acronym_endpoint(
    body: AcronymCreate,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a single acronym entry."""
    row = await create_acronym(db, body.acronym, body.spelled_out, user)
    await db.commit()
    await db.refresh(row)
    return {"data": AcronymOut.model_validate(row).model_dump(mode="json")}


@router.post("/acronyms/bulk")
async def create_acronyms_bulk_endpoint(
    body: AcronymBulkCreate,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Bulk create from upload/paste. Skips duplicates."""
    items = [{"acronym": i.acronym, "spelled_out": i.spelled_out} for i in body.items]
    count = await create_acronyms_bulk(db, items, user)
    await db.commit()
    return {"data": {"inserted": count}}


# ── Update ──


@router.patch("/acronyms/{acronym_uid}")
async def update_acronym_endpoint(
    acronym_uid: UUID,
    body: AcronymUpdate,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update an acronym. Checks row lock first."""
    kwargs: dict = {}
    if body.acronym is not None:
        kwargs["acronym"] = body.acronym
    if body.spelled_out is not None:
        kwargs["spelled_out"] = body.spelled_out
    row = await update_acronym(db, acronym_uid, user, **kwargs)
    await db.commit()
    await db.refresh(row)
    return {"data": AcronymOut.model_validate(row).model_dump(mode="json")}


# ── Delete ──


@router.delete("/acronyms/bulk-delete")
async def delete_acronyms_bulk_endpoint(
    body: AcronymBulkDelete,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete multiple acronyms by UID."""
    deleted = await delete_acronyms_bulk(db, body.acronym_uids, user)
    await db.commit()
    return {"data": {"deleted": deleted}}


@router.delete("/acronyms/{acronym_uid}")
async def delete_acronym_endpoint(
    acronym_uid: UUID,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a single acronym by UID."""
    deleted = await delete_acronyms_bulk(db, [acronym_uid], user)
    await db.commit()
    return {"data": {"deleted": deleted}}


# ── Locking ──


@router.post("/acronyms/{acronym_uid}/lock")
async def lock_acronym_endpoint(
    acronym_uid: UUID,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Acquire row lock for editing."""
    acquired = await acquire_lock(db, acronym_uid, user)
    await db.commit()
    if not acquired:
        return {"data": {"locked": False, "message": "Row is locked by another user"}}
    return {"data": {"locked": True}}


@router.post("/acronyms/{acronym_uid}/unlock")
async def unlock_acronym_endpoint(
    acronym_uid: UUID,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Release row lock."""
    await release_lock(db, acronym_uid, user)
    await db.commit()
    return {"data": {"unlocked": True}}


# ── Corpus scan ──


@router.post("/acronyms/scan-corpus")
async def scan_corpus_endpoint(
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Scan all published facts for unknown acronyms."""
    result = await scan_and_insert(db, user)
    await db.commit()
    return {"data": result}


# ── AI lookup (magic wand) ──


@router.post("/acronyms/{acronym_uid}/lookup")
async def lookup_acronym_endpoint(
    acronym_uid: UUID,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Ask AI to expand an unresolved acronym using corpus context."""
    expansion = await lookup_acronym_expansion(db, acronym_uid, user)
    await db.commit()
    return {"data": {"expansion": expansion}}


# ── Seed (admin only) ──


@router.post("/acronyms/seed")
async def seed_acronyms_endpoint(
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Seed acronyms from CSV. Admin only."""
    if user.global_role != "admin":
        raise Forbidden("Admin access required", code="ADMIN_REQUIRED")
    count = await seed_acronyms(db)
    await db.commit()
    return {"data": {"inserted": count}}
