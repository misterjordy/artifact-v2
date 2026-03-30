"""Move proposal/approval service for facts and node subtrees."""

import uuid
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.events import publish
from artiFACT.kernel.exceptions import Conflict, Forbidden, NotFound
from artiFACT.kernel.models import FcEventLog, FcFact, FcNode, FcUser
from artiFACT.kernel.permissions.resolver import can
from artiFACT.kernel.tree.descendants import get_descendants

log = structlog.get_logger()


async def propose_fact_move(
    db: AsyncSession,
    fact_uid: UUID,
    target_node_uid: UUID,
    comment: str,
    actor: FcUser,
    *,
    auto_approve: bool = False,
) -> dict[str, Any]:
    """Propose or auto-execute moving a single fact to a different node."""
    fact = await db.get(FcFact, fact_uid)
    if not fact:
        raise NotFound("Fact not found", code="FACT_NOT_FOUND")
    if fact.is_retired:
        raise Conflict("Cannot move a retired fact", code="FACT_RETIRED")
    if fact.node_uid == target_node_uid:
        raise Conflict("Fact is already in target node", code="SAME_NODE")

    target = await db.get(FcNode, target_node_uid)
    if not target:
        raise NotFound("Target node not found", code="NODE_NOT_FOUND")
    if target.is_archived:
        raise Conflict("Target node is archived", code="NODE_ARCHIVED")

    if not await can(actor, "contribute", fact.node_uid, db):
        raise Forbidden("No permission on source node", code="FORBIDDEN")
    if not await can(actor, "contribute", target_node_uid, db):
        raise Forbidden("No permission on target node", code="FORBIDDEN")

    source_node_uid = fact.node_uid

    if auto_approve and await _can_approve_both(actor, source_node_uid, target_node_uid, db):
        return await _execute_fact_move(db, fact, source_node_uid, target_node_uid, comment, actor)

    return await _propose_fact_move_event(db, fact, source_node_uid, target_node_uid, comment, actor)


async def propose_node_move(
    db: AsyncSession,
    node_uid: UUID,
    target_parent_uid: UUID,
    comment: str,
    actor: FcUser,
    *,
    auto_approve: bool = False,
) -> dict[str, Any]:
    """Propose or auto-execute moving a node subtree under a new parent."""
    node = await db.get(FcNode, node_uid)
    if not node:
        raise NotFound("Node not found", code="NODE_NOT_FOUND")
    if node.is_archived:
        raise Conflict("Node is archived", code="NODE_ARCHIVED")
    if node.node_depth == 0:
        raise Conflict("Cannot move a root node", code="ROOT_NODE")
    if node.parent_node_uid == target_parent_uid:
        raise Conflict("Node is already under target parent", code="SAME_PARENT")

    target = await db.get(FcNode, target_parent_uid)
    if not target:
        raise NotFound("Target parent not found", code="NODE_NOT_FOUND")
    if target.is_archived:
        raise Conflict("Target parent is archived", code="NODE_ARCHIVED")

    # Prevent circular reference
    target_ancestors = await get_descendants(db, node_uid)
    if target_parent_uid in target_ancestors:
        raise Conflict("Cannot move node under its own descendant", code="CIRCULAR_MOVE")

    if not await can(actor, "contribute", node_uid, db):
        raise Forbidden("No permission on source node", code="FORBIDDEN")
    if not await can(actor, "contribute", target_parent_uid, db):
        raise Forbidden("No permission on target parent", code="FORBIDDEN")

    descendant_uids = await get_descendants(db, node_uid)
    fact_uids = await _get_facts_in_nodes(db, descendant_uids)
    correlation_id = uuid.uuid4()

    if auto_approve and await _can_approve_both(actor, node_uid, target_parent_uid, db):
        return await _execute_node_move(
            db, node, target_parent_uid, descendant_uids, fact_uids,
            correlation_id, comment, actor,
        )

    return await _propose_node_move_events(
        db, node, target_parent_uid, descendant_uids, fact_uids,
        correlation_id, comment, actor,
    )


async def approve_move(
    db: AsyncSession,
    event_uid: UUID,
    actor: FcUser,
    *,
    note: str | None = None,
) -> dict[str, Any]:
    """Approve a pending move. For node moves, moves all non-rejected facts."""
    event = await db.get(FcEventLog, event_uid)
    if not event or event.event_type != "move.proposed":
        raise NotFound("Move proposal not found", code="MOVE_NOT_FOUND")

    payload = event.payload or {}
    target_uid = UUID(payload["target_node_uid"])

    if not await can(actor, "approve", target_uid, db):
        raise Forbidden("No approval permission on target", code="FORBIDDEN")

    if event.entity_type == "fact":
        return await _approve_single_fact_move(db, event, actor, note)
    elif event.entity_type == "node":
        return await _approve_node_move(db, event, actor, note)
    else:
        raise Conflict("Unknown move entity type", code="BAD_ENTITY")


async def reject_move(
    db: AsyncSession,
    event_uid: UUID,
    actor: FcUser,
    *,
    note: str | None = None,
) -> dict[str, Any]:
    """Reject an entire move proposal."""
    event = await db.get(FcEventLog, event_uid)
    if not event or event.event_type != "move.proposed":
        raise NotFound("Move proposal not found", code="MOVE_NOT_FOUND")

    payload = event.payload or {}
    target_uid = UUID(payload["target_node_uid"])

    if not await can(actor, "approve", target_uid, db):
        raise Forbidden("No approval permission on target", code="FORBIDDEN")

    event.event_type = "move.rejected"
    event.note = note

    # If it's a node move, reject all correlated fact events too
    correlation_id = (payload or {}).get("correlation_id")
    if correlation_id and event.entity_type == "node":
        await _reject_correlated_facts(db, correlation_id, note)

    return {"status": "rejected"}


async def reject_move_fact(
    db: AsyncSession,
    event_uid: UUID,
    actor: FcUser,
    *,
    note: str | None = None,
) -> dict[str, Any]:
    """Reject a single fact within a node subtree move."""
    event = await db.get(FcEventLog, event_uid)
    if not event or event.event_type != "move.proposed":
        raise NotFound("Move proposal not found", code="MOVE_NOT_FOUND")
    if event.entity_type != "fact":
        raise Conflict("Can only reject individual facts", code="BAD_ENTITY")

    payload = event.payload or {}
    target_uid = UUID(payload["target_node_uid"])

    if not await can(actor, "approve", target_uid, db):
        raise Forbidden("No approval permission on target", code="FORBIDDEN")

    event.event_type = "move.rejected"
    event.note = note

    return {"status": "rejected"}


async def get_pending_moves(
    db: AsyncSession,
    node_uids: list[UUID],
) -> list[dict[str, Any]]:
    """Return pending move proposals where target is in scope."""
    if not node_uids:
        return []

    stmt = (
        select(FcEventLog)
        .where(
            FcEventLog.event_type == "move.proposed",
        )
        .order_by(FcEventLog.occurred_at.asc())
    )
    result = await db.execute(stmt)
    events = result.scalars().all()

    uid_set = set(node_uids)
    moves: list[dict[str, Any]] = []
    for evt in events:
        payload = evt.payload or {}
        target_str = payload.get("target_node_uid")
        if not target_str:
            continue
        if UUID(target_str) not in uid_set:
            continue
        moves.append({
            "event_uid": evt.event_uid,
            "entity_type": evt.entity_type,
            "entity_uid": evt.entity_uid,
            "event_type": evt.event_type,
            "payload": payload,
            "actor_uid": evt.actor_uid,
            "occurred_at": evt.occurred_at,
            "correlation_id": payload.get("correlation_id"),
        })
    return moves


# ── Private helpers ──


async def _can_approve_both(
    actor: FcUser, source_uid: UUID, target_uid: UUID, db: AsyncSession,
) -> bool:
    """Check approve permission on both source and target nodes."""
    src = await can(actor, "approve", source_uid, db)
    tgt = await can(actor, "approve", target_uid, db)
    return src and tgt


async def _get_facts_in_nodes(
    db: AsyncSession, node_uids: list[UUID],
) -> list[UUID]:
    """Return all non-retired fact UIDs under a set of nodes."""
    if not node_uids:
        return []
    stmt = (
        select(FcFact.fact_uid)
        .where(FcFact.node_uid.in_(node_uids), FcFact.is_retired.is_(False))
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


async def _execute_fact_move(
    db: AsyncSession,
    fact: FcFact,
    source_node_uid: UUID,
    target_node_uid: UUID,
    comment: str,
    actor: FcUser,
) -> dict[str, Any]:
    """Execute a fact move immediately (auto-approve path)."""
    fact.node_uid = target_node_uid

    event_uid = uuid.uuid4()
    await publish("move.approved", {
        "event_uid": str(event_uid),
        "entity_type": "fact",
        "entity_uid": str(fact.fact_uid),
        "source_node_uid": str(source_node_uid),
        "target_node_uid": str(target_node_uid),
        "comment": comment,
        "actor_uid": str(actor.user_uid),
    })
    return {"status": "moved", "event_uid": str(event_uid)}


async def _propose_fact_move_event(
    db: AsyncSession,
    fact: FcFact,
    source_node_uid: UUID,
    target_node_uid: UUID,
    comment: str,
    actor: FcUser,
) -> dict[str, Any]:
    """Create a move.proposed event for a single fact."""
    event_uid = uuid.uuid4()
    await publish("move.proposed", {
        "event_uid": str(event_uid),
        "entity_type": "fact",
        "entity_uid": str(fact.fact_uid),
        "source_node_uid": str(source_node_uid),
        "target_node_uid": str(target_node_uid),
        "comment": comment,
        "actor_uid": str(actor.user_uid),
    })
    return {"status": "proposed", "event_uid": str(event_uid)}


async def _execute_node_move(
    db: AsyncSession,
    node: FcNode,
    target_parent_uid: UUID,
    descendant_uids: list[UUID],
    fact_uids: list[UUID],
    correlation_id: uuid.UUID,
    comment: str,
    actor: FcUser,
) -> dict[str, Any]:
    """Execute a node reparent immediately (auto-approve path)."""
    old_parent_uid = node.parent_node_uid
    node.parent_node_uid = target_parent_uid
    await _recompute_depths(db, node, descendant_uids)

    for fuid in fact_uids:
        await publish("move.approved", {
            "entity_type": "fact",
            "entity_uid": str(fuid),
            "source_node_uid": str(old_parent_uid),
            "target_node_uid": str(target_parent_uid),
            "correlation_id": str(correlation_id),
            "comment": comment,
            "actor_uid": str(actor.user_uid),
        })

    return {
        "status": "moved",
        "fact_count": len(fact_uids),
        "correlation_id": str(correlation_id),
    }


async def _propose_node_move_events(
    db: AsyncSession,
    node: FcNode,
    target_parent_uid: UUID,
    descendant_uids: list[UUID],
    fact_uids: list[UUID],
    correlation_id: uuid.UUID,
    comment: str,
    actor: FcUser,
) -> dict[str, Any]:
    """Create move.proposed events for a node and all its facts."""
    node_event_uid = uuid.uuid4()

    # Node-level event
    await publish("move.proposed", {
        "event_uid": str(node_event_uid),
        "entity_type": "node",
        "entity_uid": str(node.node_uid),
        "source_parent_uid": str(node.parent_node_uid),
        "target_node_uid": str(target_parent_uid),
        "affected_fact_uids": [str(u) for u in fact_uids],
        "affected_node_uids": [str(u) for u in descendant_uids],
        "correlation_id": str(correlation_id),
        "comment": comment,
        "actor_uid": str(actor.user_uid),
    })

    # Per-fact events
    for fuid in fact_uids:
        await publish("move.proposed", {
            "entity_type": "fact",
            "entity_uid": str(fuid),
            "source_node_uid": str(node.node_uid),
            "target_node_uid": str(target_parent_uid),
            "correlation_id": str(correlation_id),
            "comment": comment,
            "actor_uid": str(actor.user_uid),
        })

    return {
        "status": "proposed",
        "event_uid": str(node_event_uid),
        "fact_count": len(fact_uids),
        "correlation_id": str(correlation_id),
    }


async def _approve_single_fact_move(
    db: AsyncSession,
    event: FcEventLog,
    actor: FcUser,
    note: str | None,
) -> dict[str, Any]:
    """Approve a single fact move proposal."""
    payload = event.payload or {}
    fact_uid = UUID(payload["entity_uid"])
    target_uid = UUID(payload["target_node_uid"])

    fact = await db.get(FcFact, fact_uid)
    if not fact:
        raise NotFound("Fact not found", code="FACT_NOT_FOUND")

    fact.node_uid = target_uid
    event.event_type = "move.approved"
    event.note = note

    return {"status": "approved", "moved_count": 1, "rejected_count": 0}


async def _approve_node_move(
    db: AsyncSession,
    event: FcEventLog,
    actor: FcUser,
    note: str | None,
) -> dict[str, Any]:
    """Approve a node move — move all non-rejected facts, reparent node."""
    payload = event.payload or {}
    node_uid = UUID(payload["entity_uid"])
    target_uid = UUID(payload["target_node_uid"])
    correlation_id = payload.get("correlation_id")

    node = await db.get(FcNode, node_uid)
    if not node:
        raise NotFound("Node not found", code="NODE_NOT_FOUND")

    # Find correlated fact events
    moved = 0
    rejected = 0
    if correlation_id:
        stmt = (
            select(FcEventLog)
            .where(FcEventLog.entity_type == "fact")
            .order_by(FcEventLog.occurred_at.asc())
        )
        result = await db.execute(stmt)
        for fact_evt in result.scalars().all():
            fp = fact_evt.payload or {}
            if fp.get("correlation_id") != correlation_id:
                continue
            if fact_evt.event_type == "move.rejected":
                rejected += 1
                continue
            if fact_evt.event_type != "move.proposed":
                continue

            fuid = UUID(fp["entity_uid"])
            fact = await db.get(FcFact, fuid)
            if fact:
                fact.node_uid = target_uid
                fact_evt.event_type = "move.approved"
                moved += 1

    # Reparent node and recompute depths
    node.parent_node_uid = target_uid
    descendant_uids = await get_descendants(db, node_uid)
    await _recompute_depths(db, node, descendant_uids)

    event.event_type = "move.approved"
    event.note = note

    return {"status": "approved", "moved_count": moved, "rejected_count": rejected}


async def _recompute_depths(
    db: AsyncSession, node: FcNode, descendant_uids: list[UUID],
) -> None:
    """Recompute node_depth for a node and all its descendants."""
    # Determine new depth from parent
    if node.parent_node_uid:
        parent = await db.get(FcNode, node.parent_node_uid)
        new_depth = (parent.node_depth + 1) if parent else 0
    else:
        new_depth = 0

    old_depth = node.node_depth
    delta = new_depth - old_depth
    node.node_depth = new_depth

    if delta != 0:
        for desc_uid in descendant_uids:
            if desc_uid == node.node_uid:
                continue
            desc = await db.get(FcNode, desc_uid)
            if desc:
                desc.node_depth = desc.node_depth + delta


async def _reject_correlated_facts(
    db: AsyncSession, correlation_id: str, note: str | None,
) -> None:
    """Reject all pending fact-level events sharing a correlation_id."""
    stmt = (
        select(FcEventLog)
        .where(
            FcEventLog.event_type == "move.proposed",
            FcEventLog.entity_type == "fact",
        )
    )
    result = await db.execute(stmt)
    for evt in result.scalars().all():
        fp = evt.payload or {}
        if fp.get("correlation_id") == correlation_id:
            evt.event_type = "move.rejected"
            evt.note = note
