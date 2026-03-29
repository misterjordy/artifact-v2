"""Approval/rejection logic with scope enforcement and transactions."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.events import publish
from artiFACT.kernel.exceptions import Conflict, Forbidden, NotFound
from artiFACT.kernel.models import FcFact, FcFactVersion, FcUser
from artiFACT.modules.facts.state_machine import transition
from artiFACT.modules.queue.scope_resolver import get_approvable_nodes


async def approve_proposal(
    db: AsyncSession,
    version_uid: uuid.UUID,
    actor: FcUser,
    *,
    note: str | None = None,
) -> FcFactVersion:
    """Approve a proposed version: scope check → transaction → event."""
    version = await db.get(FcFactVersion, version_uid)
    if not version:
        raise NotFound("Version not found")
    if version.state != "proposed":
        raise Conflict("Not a pending proposal")

    fact = await db.get(FcFact, version.fact_uid)
    if not fact:
        raise NotFound("Fact not found")

    approvable = await get_approvable_nodes(db, actor)
    if fact.node_uid not in approvable:
        raise Forbidden("This fact is outside your approval scope")

    async with db.begin_nested():
        await transition(version, "published", actor)
        fact.current_published_version_uid = version.version_uid

    await publish(
        "version.approved",
        {
            "version_uid": str(version.version_uid),
            "fact_uid": str(version.fact_uid),
            "actor_uid": str(actor.user_uid),
            "note": note,
        },
    )

    return version


async def reject_proposal(
    db: AsyncSession,
    version_uid: uuid.UUID,
    actor: FcUser,
    *,
    note: str | None = None,
) -> FcFactVersion:
    """Reject a proposed version: scope check → transaction → event."""
    version = await db.get(FcFactVersion, version_uid)
    if not version:
        raise NotFound("Version not found")
    if version.state != "proposed":
        raise Conflict("Not a pending proposal")

    fact = await db.get(FcFact, version.fact_uid)
    if not fact:
        raise NotFound("Fact not found")

    approvable = await get_approvable_nodes(db, actor)
    if fact.node_uid not in approvable:
        raise Forbidden("This fact is outside your approval scope")

    async with db.begin_nested():
        await transition(version, "rejected", actor)

    await publish(
        "version.rejected",
        {
            "version_uid": str(version.version_uid),
            "fact_uid": str(version.fact_uid),
            "actor_uid": str(actor.user_uid),
            "note": note,
        },
    )

    return version


async def approve_move(
    db: AsyncSession,
    event_uid: uuid.UUID,
    actor: FcUser,
    *,
    note: str | None = None,
) -> FcFact:
    """Approve a move proposal: scope check on target node → execute move."""
    from artiFACT.kernel.models import FcEventLog

    event = await db.get(FcEventLog, event_uid)
    if not event or event.event_type != "fact.move_proposed":
        raise NotFound("Move proposal not found")

    payload = event.payload or {}
    target_uid = uuid.UUID(payload["target_node_uid"])
    fact_uid = uuid.UUID(payload["fact_uid"])

    approvable = await get_approvable_nodes(db, actor)
    if target_uid not in approvable:
        raise Forbidden("Target node is outside your approval scope")

    fact = await db.get(FcFact, fact_uid)
    if not fact:
        raise NotFound("Fact not found")

    async with db.begin_nested():
        old_node_uid = fact.node_uid
        fact.node_uid = target_uid
        event.event_type = "fact.move_approved"

    await publish(
        "fact.moved",
        {
            "fact_uid": str(fact_uid),
            "old_node_uid": str(old_node_uid),
            "new_node_uid": str(target_uid),
            "actor_uid": str(actor.user_uid),
        },
    )

    return fact


async def reject_move(
    db: AsyncSession,
    event_uid: uuid.UUID,
    actor: FcUser,
    *,
    note: str | None = None,
) -> None:
    """Reject a move proposal: scope check → mark as rejected."""
    from artiFACT.kernel.models import FcEventLog

    event = await db.get(FcEventLog, event_uid)
    if not event or event.event_type != "fact.move_proposed":
        raise NotFound("Move proposal not found")

    payload = event.payload or {}
    target_uid = uuid.UUID(payload["target_node_uid"])

    approvable = await get_approvable_nodes(db, actor)
    if target_uid not in approvable:
        raise Forbidden("Target node is outside your approval scope")

    async with db.begin_nested():
        event.event_type = "fact.move_rejected"
        event.note = note
