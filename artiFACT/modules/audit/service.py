"""Audit service — flush pending events to database."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcEventLog
from artiFACT.modules.audit.recorder import get_pending_events


async def flush_pending_events(db: AsyncSession) -> list[FcEventLog]:
    """Write all pending events from the recorder buffer to the database."""
    events = get_pending_events()
    for event in events:
        db.add(event)
    if events:
        await db.flush()
    return events


async def get_events_for_entity(db: AsyncSession, entity_uid: str) -> list[FcEventLog]:
    """Return all events for an entity, newest first."""
    stmt = (
        select(FcEventLog)
        .where(FcEventLog.entity_uid == entity_uid)
        .order_by(FcEventLog.occurred_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_all_events(
    db: AsyncSession,
    *,
    entity_type: str | None = None,
    event_type: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[FcEventLog], int]:
    """Return filtered events with pagination."""
    stmt = select(FcEventLog)
    count_stmt = select(FcEventLog.event_uid)
    if entity_type:
        stmt = stmt.where(FcEventLog.entity_type == entity_type)
        count_stmt = count_stmt.where(FcEventLog.entity_type == entity_type)
    if event_type:
        stmt = stmt.where(FcEventLog.event_type == event_type)
        count_stmt = count_stmt.where(FcEventLog.event_type == event_type)

    total = len((await db.execute(count_stmt)).all())
    stmt = stmt.order_by(FcEventLog.occurred_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all()), total
