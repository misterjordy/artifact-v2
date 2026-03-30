"""Execute undo operations via reverse_payload."""

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Conflict, Forbidden, NotFound
from artiFACT.kernel.models import (
    FcEventLog,
    FcFact,
    FcFactComment,
    FcFactVersion,
    FcNode,
    FcNodePermission,
    FcUser,
)
from artiFACT.kernel.permissions.resolver import can
from artiFACT.modules.audit.collision_checker import check_collision_strict

log = structlog.get_logger()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def undo_event(
    db: AsyncSession, event_uid: UUID, actor: FcUser,
) -> dict[str, str]:
    """Undo a single event.

    Validates ownership, reversibility, collision, and permission.
    Dispatches through owning module service layer.
    Records an undo audit event referencing the original.
    """
    event = await db.get(FcEventLog, event_uid)
    if not event:
        raise NotFound("Event not found", code="EVENT_NOT_FOUND")

    _validate_undoable(event, actor)

    node_uid = await _resolve_entity_node(db, event)
    await _check_permission(actor, node_uid, event, db)

    await check_collision_strict(db, event)

    reverse = event.reverse_payload
    detail = await _dispatch_undo(db, reverse, actor)

    # Mark original event as undone
    event.undone_at = _utcnow()
    event.undone_by_uid = actor.user_uid

    # Record an 'undo' audit event
    undo_record = FcEventLog(
        entity_type=event.entity_type,
        entity_uid=event.entity_uid,
        event_type="undo",
        payload={"original_event_uid": str(event.event_uid), "action": reverse["action"]},
        actor_uid=str(actor.user_uid),
        reversible=False,
    )
    db.add(undo_record)

    return {"status": "undone", "event_uid": str(event.event_uid), "detail": detail}


async def undo_bulk(
    db: AsyncSession, event_uids: list[UUID], actor: FcUser,
) -> dict:
    """Undo a group of events atomically.

    All events must belong to the actor. All must pass collision check.
    If any single event fails validation, the entire batch fails.
    """
    if not event_uids:
        raise Conflict("No events to undo", code="EMPTY_BATCH")

    events: list[FcEventLog] = []
    for uid in event_uids:
        event = await db.get(FcEventLog, uid)
        if not event:
            raise NotFound(f"Event {uid} not found", code="EVENT_NOT_FOUND")
        events.append(event)

    # Validate all before executing any
    for event in events:
        _validate_undoable(event, actor)

    for event in events:
        node_uid = await _resolve_entity_node(db, event)
        await _check_permission(actor, node_uid, event, db)

    for event in events:
        await check_collision_strict(db, event)

    # Execute all undos
    details: list[str] = []
    for event in events:
        reverse = event.reverse_payload
        detail = await _dispatch_undo(db, reverse, actor)
        event.undone_at = _utcnow()
        event.undone_by_uid = actor.user_uid
        undo_record = FcEventLog(
            entity_type=event.entity_type,
            entity_uid=event.entity_uid,
            event_type="undo",
            payload={"original_event_uid": str(event.event_uid), "action": reverse["action"]},
            actor_uid=str(actor.user_uid),
            reversible=False,
        )
        db.add(undo_record)
        details.append(detail)

    return {"status": "undone", "count": len(events), "details": details}


# ── Validation helpers ──


def _validate_undoable(event: FcEventLog, actor: FcUser) -> None:
    """Check ownership, reversibility, and undone status."""
    if event.undone_at is not None:
        raise Conflict("Already undone", code="ALREADY_UNDONE")
    if not event.reversible:
        raise Conflict("This action is not reversible", code="NOT_REVERSIBLE")
    if str(event.actor_uid) != str(actor.user_uid):
        raise Forbidden("Can only undo your own actions", code="FORBIDDEN")
    if not event.reverse_payload:
        raise Conflict("Event has no reverse payload", code="NO_REVERSE_PAYLOAD")


async def _check_permission(
    actor: FcUser, node_uid: UUID | None, event: FcEventLog, db: AsyncSession,
) -> None:
    """Check the actor still has permission on the entity's node."""
    if node_uid is None:
        return
    action_required = _permission_for_undo(event)
    if not await can(actor, action_required, node_uid, db):
        raise Forbidden(
            "You no longer have permission on this entity", code="FORBIDDEN",
        )


def _permission_for_undo(event: FcEventLog) -> str:
    """Determine what permission level is needed to undo this event type."""
    rp = event.reverse_payload or {}
    action = rp.get("action", "")
    if action in ("withdraw", "reject_move"):
        return "contribute"
    if action in ("delete_comment",):
        return "contribute"
    return "approve"


async def _resolve_entity_node(db: AsyncSession, event: FcEventLog) -> UUID | None:
    """Resolve the node_uid for the entity referenced by an event."""
    rp = event.reverse_payload or {}
    action = rp.get("action", "")

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
    elif event.entity_type == "node":
        return UUID(str(event.entity_uid))
    elif event.entity_type == "permission":
        perm = await db.get(FcNodePermission, event.entity_uid)
        if perm:
            return perm.node_uid
    elif event.entity_type == "comment":
        comment = await db.get(FcFactComment, event.entity_uid)
        if comment:
            version = await db.get(FcFactVersion, comment.version_uid)
            if version:
                fact = await db.get(FcFact, version.fact_uid)
                if fact:
                    return fact.node_uid

    # For some undo actions, try reverse_payload
    if action in ("unretire", "retire", "restore_version"):
        fact_uid = rp.get("fact_uid")
        if fact_uid:
            fact = await db.get(FcFact, UUID(fact_uid))
            if fact:
                return fact.node_uid
    if action == "move_back":
        return UUID(rp["original_node_uid"])
    if action == "move":
        # Backward compat: old format
        return UUID(rp["target_node_uid"])
    if action in ("archive_node", "unarchive_node"):
        return UUID(rp["node_uid"])

    raise NotFound("Entity not found for permission check", code="ENTITY_GONE")


# ── Undo dispatch ──


async def _dispatch_undo(
    db: AsyncSession, reverse: dict, actor: FcUser,
) -> str:
    """Dispatch the undo action through the owning module's service layer."""
    action = reverse["action"]

    if action == "withdraw":
        return await _undo_withdraw(db, reverse, actor)
    if action == "unretire":
        return await _undo_unretire(db, reverse, actor)
    if action == "retire":
        return await _undo_retire(db, reverse, actor)
    if action == "restore_version":
        return await _undo_restore_version(db, reverse, actor)
    if action == "move_back":
        return await _undo_move_back(db, reverse, actor)
    if action == "move":
        return await _undo_move_legacy(db, reverse, actor)
    if action == "reject_move":
        return await _undo_reject_move(db, reverse, actor)
    if action == "unreject":
        return await _undo_unreject(db, reverse, actor)
    if action == "archive_node":
        return await _undo_archive_node(db, reverse, actor)
    if action == "unarchive_node":
        return await _undo_unarchive_node(db, reverse, actor)
    if action == "revoke_grant":
        return await _undo_revoke_grant(db, reverse, actor)
    if action == "restore_grant":
        return await _undo_restore_grant(db, reverse, actor)
    if action == "delete_comment":
        return await _undo_delete_comment(db, reverse)

    raise Conflict(f"Unknown undo action: {action}", code="UNKNOWN_ACTION")


async def _undo_withdraw(
    db: AsyncSession, rp: dict, actor: FcUser,
) -> str:
    """Withdraw a proposed fact version."""
    from artiFACT.modules.facts.state_machine import transition

    version = await db.get(FcFactVersion, UUID(rp["version_uid"]))
    if not version:
        raise NotFound("Version not found", code="VERSION_NOT_FOUND")
    await transition(version, "withdrawn", actor)
    return "Withdrew proposal"


async def _undo_unretire(
    db: AsyncSession, rp: dict, actor: FcUser,
) -> str:
    """Unretire a fact via the facts service."""
    from artiFACT.modules.facts.service import unretire_fact

    await unretire_fact(db, UUID(rp["fact_uid"]), actor)
    return "Unretired fact"


async def _undo_retire(
    db: AsyncSession, rp: dict, actor: FcUser,
) -> str:
    """Re-retire a fact via the facts service."""
    from artiFACT.modules.facts.service import retire_fact

    await retire_fact(db, UUID(rp["fact_uid"]), actor)
    return "Re-retired fact"


async def _undo_restore_version(
    db: AsyncSession, rp: dict, actor: FcUser,
) -> str:
    """Restore a previous version as current."""
    fact = await db.get(FcFact, UUID(rp["fact_uid"]))
    if not fact:
        raise NotFound("Fact not found", code="FACT_NOT_FOUND")
    prev_uid = UUID(rp["previous_version_uid"])
    prev = await db.get(FcFactVersion, prev_uid)
    if not prev:
        raise NotFound("Previous version not found", code="VERSION_NOT_FOUND")
    fact.current_published_version_uid = prev_uid
    return "Restored previous version"


async def _undo_reject_move(
    db: AsyncSession, rp: dict, actor: FcUser,
) -> str:
    """Cancel a pending move proposal by rejecting it."""
    from artiFACT.modules.facts.move_service import reject_move

    event_uid = UUID(rp["event_uid"])
    await reject_move(db, event_uid, actor, note="Cancelled by undo")
    return "Cancelled move proposal"


async def _undo_move_legacy(
    db: AsyncSession, rp: dict, actor: FcUser,
) -> str:
    """Backward compat: old format {"action":"move","fact_uid":...,"target_node_uid":...}."""
    from artiFACT.modules.facts.reassign import reassign_fact

    fact_uid = UUID(rp.get("fact_uid") or rp["entity_uid"])
    target_uid = UUID(rp["target_node_uid"])
    await reassign_fact(db, fact_uid, target_uid, actor)
    return "Moved fact back"


async def _undo_move_back(
    db: AsyncSession, rp: dict, actor: FcUser,
) -> str:
    """Move entity back to its original location."""
    entity_type = rp.get("entity_type", "fact")
    entity_uid = UUID(rp["entity_uid"])
    original_uid = UUID(rp["original_node_uid"])

    if entity_type == "node":
        from artiFACT.modules.taxonomy.service import move_node

        await move_node(db, entity_uid, original_uid, actor)
        return "Moved node back"
    else:
        from artiFACT.modules.facts.reassign import reassign_fact

        await reassign_fact(db, entity_uid, original_uid, actor)
        return "Moved fact back"


async def _undo_unreject(
    db: AsyncSession, rp: dict, actor: FcUser,
) -> str:
    """Restore a rejected version to proposed state."""
    from artiFACT.modules.facts.state_machine import transition

    version = await db.get(FcFactVersion, UUID(rp["version_uid"]))
    if not version:
        raise NotFound("Version not found", code="VERSION_NOT_FOUND")
    await transition(version, rp["restore_state"], actor)
    return "Restored proposal from rejected"


async def _undo_archive_node(
    db: AsyncSession, rp: dict, actor: FcUser,
) -> str:
    """Archive a node (undo of node creation)."""
    from artiFACT.modules.taxonomy.service import archive_node

    await archive_node(db, UUID(rp["node_uid"]), actor)
    return "Archived node"


async def _undo_unarchive_node(
    db: AsyncSession, rp: dict, actor: FcUser,
) -> str:
    """Unarchive a node."""
    node = await db.get(FcNode, UUID(rp["node_uid"]))
    if not node:
        raise NotFound("Node not found", code="NODE_NOT_FOUND")
    node.is_archived = False
    return "Unarchived node"


async def _undo_revoke_grant(
    db: AsyncSession, rp: dict, actor: FcUser,
) -> str:
    """Revoke a permission grant."""
    perm = await db.get(FcNodePermission, UUID(rp["permission_uid"]))
    if not perm:
        raise NotFound("Permission not found", code="PERM_NOT_FOUND")
    perm.revoked_at = _utcnow()
    return "Revoked permission"


async def _undo_restore_grant(
    db: AsyncSession, rp: dict, actor: FcUser,
) -> str:
    """Restore a revoked permission."""
    perm = await db.get(FcNodePermission, UUID(rp["permission_uid"]))
    if not perm:
        raise NotFound("Permission not found", code="PERM_NOT_FOUND")
    perm.revoked_at = None
    return "Restored permission"


async def _undo_delete_comment(db: AsyncSession, rp: dict) -> str:
    """Soft-delete a comment."""
    comment = await db.get(FcFactComment, UUID(rp["comment_uid"]))
    if not comment:
        raise NotFound("Comment not found", code="COMMENT_NOT_FOUND")
    await db.delete(comment)
    return "Deleted comment"
