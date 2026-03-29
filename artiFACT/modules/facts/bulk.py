"""Batch operations on facts (all-or-nothing transactions)."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcUser
from artiFACT.modules.facts.reassign import reassign_fact
from artiFACT.modules.facts.service import retire_fact


async def bulk_retire(
    db: AsyncSession, fact_uids: list[UUID], actor: FcUser
) -> list[UUID]:
    """Retire multiple facts. All-or-nothing: if any fails, none retire."""
    retired = []
    for uid in fact_uids:
        await retire_fact(db, uid, actor)
        retired.append(uid)
    return retired


async def bulk_move(
    db: AsyncSession,
    fact_uids: list[UUID],
    target_node_uid: UUID,
    actor: FcUser,
) -> list[UUID]:
    """Move multiple facts to a target node. All-or-nothing."""
    moved = []
    for uid in fact_uids:
        await reassign_fact(db, uid, target_node_uid, actor)
        moved.append(uid)
    return moved
