"""Audit API endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.db import get_db
from artiFACT.kernel.models import FcUser
from artiFACT.modules.audit.schemas import EventOut, UndoResult
from artiFACT.modules.audit.service import get_all_events, get_events_for_entity
from artiFACT.modules.audit.undo_engine import undo_event

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/events")
async def list_events(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
    entity_type: str | None = Query(None),
    event_type: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """Return audit events with filtering."""
    events, total = await get_all_events(
        db,
        entity_type=entity_type,
        event_type=event_type,
        offset=offset,
        limit=limit,
    )
    data = [EventOut.model_validate(e) for e in events]
    return {
        "data": [d.model_dump(mode="json") for d in data],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/events/{event_uid}")
async def get_event(
    event_uid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> EventOut:
    """Return a single event detail."""
    from artiFACT.kernel.exceptions import NotFound
    from artiFACT.kernel.models import FcEventLog

    event = await db.get(FcEventLog, event_uid)
    if not event:
        raise NotFound("Event not found", code="EVENT_NOT_FOUND")
    return EventOut.model_validate(event)


@router.get("/history/{entity_uid}")
async def entity_history(
    entity_uid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict:
    """Return full timeline for an entity."""
    events = await get_events_for_entity(db, str(entity_uid))
    data = [EventOut.model_validate(e) for e in events]
    return {"data": [d.model_dump(mode="json") for d in data], "total": len(data)}


@router.post("/undo/{event_uid}")
async def undo(
    event_uid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> UndoResult:
    """Undo a specific action."""
    event = await undo_event(db, event_uid, user)
    await db.commit()
    return UndoResult(event_uid=event.event_uid, message="Action undone successfully")
