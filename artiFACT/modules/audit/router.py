"""Audit API endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.db import get_db
from artiFACT.kernel.models import FcUser
from artiFACT.modules.audit.schemas import (
    BulkUndoRequest,
    EventOut,
    UndoActionsResponse,
    UndoResponse,
)
from artiFACT.modules.audit.service import get_all_events, get_events_for_entity

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])

undo_router = APIRouter(prefix="/api/v1/undo", tags=["undo"])


# ── Audit endpoints ──


@router.get("/events")
async def list_events(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
    entity_type: str | None = Query(None),
    event_type: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
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
) -> dict[str, Any]:
    """Return full timeline for an entity."""
    events = await get_events_for_entity(db, str(entity_uid))
    data = [EventOut.model_validate(e) for e in events]
    return {"data": [d.model_dump(mode="json") for d in data], "total": len(data)}


# ── Undo endpoints ──


@undo_router.get("/actions")
async def list_undo_actions(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
    days: int = Query(30, ge=1, le=30),
) -> UndoActionsResponse:
    """Return the user's undoable actions within the time window."""
    from artiFACT.modules.audit.undo_actions import get_undo_actions

    actions = await get_undo_actions(db, user, days=days)
    return UndoActionsResponse(actions=actions, total=len(actions))


@undo_router.post("/{event_uid}")
async def undo_single(
    event_uid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> UndoResponse:
    """Undo a single event."""
    from artiFACT.modules.audit.undo_engine import undo_event

    result = await undo_event(db, event_uid, user)
    await db.flush()
    return UndoResponse(status=result["status"], detail=result["detail"])


@undo_router.post("/bulk")
async def undo_bulk_endpoint(
    body: BulkUndoRequest,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> UndoResponse:
    """Undo a group of events atomically."""
    from artiFACT.modules.audit.undo_engine import undo_bulk

    result = await undo_bulk(db, body.event_uids, user)
    await db.flush()
    return UndoResponse(
        status=result["status"],
        detail=f"Undid {result['count']} actions",
        count=result["count"],
        details=result["details"],
    )
