"""Execute undo/redo operations via reverse_payload."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Conflict, Forbidden, NotFound
from artiFACT.kernel.models import FcEventLog, FcFact, FcFactVersion, FcUser
from artiFACT.kernel.permissions.resolver import can
from artiFACT.modules.audit.collision_checker import check_collision
from artiFACT.modules.facts.reassign import reassign_fact
from artiFACT.modules.facts.service import unretire_fact
from artiFACT.modules.facts.state_machine import transition


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _resolve_entity_node(db: AsyncSession, event: FcEventLog) -> UUID:
    """Resolve the node_uid for the entity referenced by an event."""
    if event.entity_type == "fact":
        fact = await db.get(FcFact, event.entity_uid)
        if fact:
            return fact.node_uid
    elif event.entity_type == "version":
        version = await db.get(FcFactVersion, event.entity_uid)
        if version:
            fact = await db.get(FcFact, version.fact_uid)
            if fact:
                return fact.node_uid
    raise NotFound("Entity not found for permission check", code="ENTITY_GONE")


async def undo_event(
    db: AsyncSession, event_uid: UUID, actor: FcUser
) -> FcEventLog:
    """Undo a previously recorded event."""
    event = await db.get(FcEventLog, event_uid)
    if not event:
        raise NotFound("Event not found", code="EVENT_NOT_FOUND")
    if not event.reversible:
        raise Conflict("This action is not reversible", code="NOT_REVERSIBLE")

    if str(event.actor_uid) != str(actor.user_uid) and actor.global_role != "admin":
        raise Forbidden("Can only undo your own actions", code="FORBIDDEN")

    node_uid = await _resolve_entity_node(db, event)
    if not await can(actor, "approve", node_uid, db):
        raise Forbidden(
            "You no longer have permission on this entity", code="FORBIDDEN"
        )

    await check_collision(db, event)

    reverse = event.reverse_payload
    action = reverse["action"]

    if action == "unretire":
        await unretire_fact(db, reverse["fact_uid"], actor)
    elif action == "move":
        await reassign_fact(db, reverse["fact_uid"], reverse["target_node_uid"], actor)
    elif action == "unreject":
        version = await db.get(FcFactVersion, reverse["version_uid"])
        if not version:
            raise NotFound("Version not found", code="VERSION_NOT_FOUND")
        await transition(version, reverse["restore_state"], actor)

    event.reversible = False
    event.note = f"Undone by {actor.display_name} at {_utcnow().isoformat()}"

    return event
