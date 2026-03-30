"""Pre-check if an undo operation is safe (no state drift)."""

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Conflict, NotFound
from artiFACT.kernel.models import (
    FcEventLog,
    FcFact,
    FcFactComment,
    FcFactVersion,
    FcNode,
    FcNodePermission,
)

log = structlog.get_logger()


async def check_collision(db: AsyncSession, event: FcEventLog) -> str | None:
    """Check if the entity is safe to undo.

    Returns None if safe, or a human-readable lock reason string.
    """
    if event.undone_at is not None:
        return "Already undone"

    reverse = event.reverse_payload
    if not reverse:
        return "Event has no reverse payload"

    action = reverse.get("action")

    if action == "withdraw":
        return await _check_withdraw(db, reverse)
    if action == "unretire":
        return await _check_unretire(db, reverse)
    if action == "retire":
        return await _check_retire(db, reverse)
    if action == "restore_version":
        return await _check_restore_version(db, reverse)
    if action == "move_back":
        return await _check_move_back(db, reverse)
    if action == "move":
        return await _check_move_legacy(db, reverse)
    if action == "reject_move":
        return await _check_reject_move(db, reverse)
    if action == "unreject":
        return await _check_unreject(db, reverse)
    if action == "archive_node":
        return await _check_archive_node(db, reverse)
    if action == "unarchive_node":
        return await _check_unarchive_node(db, reverse)
    if action == "revoke_grant":
        return await _check_revoke_grant(db, reverse)
    if action == "restore_grant":
        return await _check_restore_grant(db, reverse)
    if action == "delete_comment":
        return await _check_delete_comment(db, reverse)

    return f"Unknown undo action: {action}"


async def check_collision_strict(db: AsyncSession, event: FcEventLog) -> None:
    """Raise Conflict or NotFound if the entity is not safe to undo."""
    reason = await check_collision(db, event)
    if reason is None:
        return
    if "no longer exists" in reason or "not found" in reason.lower():
        raise NotFound(reason, code="ENTITY_GONE")
    raise Conflict(reason, code="COLLISION_DETECTED")


async def batch_check_collisions(
    db: AsyncSession, events: list[FcEventLog],
) -> dict[UUID, str | None]:
    """Batch collision check for multiple events.

    Gathers all entity UIDs, fetches relevant entities in bulk,
    then checks each event against the pre-fetched data.
    """
    if not events:
        return {}

    # Collect UIDs by entity type
    fact_uids: set[UUID] = set()
    version_uids: set[UUID] = set()
    node_uids: set[UUID] = set()
    permission_uids: set[UUID] = set()
    comment_uids: set[UUID] = set()

    for event in events:
        rp = event.reverse_payload or {}
        action = rp.get("action", "")
        if action in ("unretire", "retire"):
            fact_uids.add(UUID(rp["fact_uid"]))
        elif action == "withdraw":
            if rp.get("version_uid"):
                version_uids.add(UUID(rp["version_uid"]))
        elif action == "restore_version":
            if rp.get("previous_version_uid"):
                version_uids.add(UUID(rp["previous_version_uid"]))
            fact_uids.add(UUID(rp["fact_uid"]))
        elif action == "move_back":
            uid = UUID(rp["entity_uid"])
            if rp.get("entity_type") == "node":
                node_uids.add(uid)
            else:
                fact_uids.add(uid)
            node_uids.add(UUID(rp["original_node_uid"]))
        elif action == "move":
            # Backward compat: old format before Prompt A
            if rp.get("fact_uid"):
                fact_uids.add(UUID(rp["fact_uid"]))
            if rp.get("target_node_uid"):
                node_uids.add(UUID(rp["target_node_uid"]))
        elif action == "unreject":
            version_uids.add(UUID(rp["version_uid"]))
        elif action in ("archive_node", "unarchive_node"):
            node_uids.add(UUID(rp["node_uid"]))
        elif action in ("revoke_grant", "restore_grant"):
            permission_uids.add(UUID(rp["permission_uid"]))
        elif action == "delete_comment":
            comment_uids.add(UUID(rp["comment_uid"]))

    # Bulk-fetch entities (ONE query per entity type)
    facts = await _bulk_fetch_facts(db, fact_uids) if fact_uids else {}
    versions = await _bulk_fetch_versions(db, version_uids) if version_uids else {}
    nodes = await _bulk_fetch_nodes(db, node_uids) if node_uids else {}
    perms = await _bulk_fetch_permissions(db, permission_uids) if permission_uids else {}
    comments = await _bulk_fetch_comments(db, comment_uids) if comment_uids else {}

    results: dict[UUID, str | None] = {}
    for event in events:
        if event.undone_at is not None:
            results[event.event_uid] = "Already undone"
            continue
        rp = event.reverse_payload
        if not rp:
            results[event.event_uid] = "Event has no reverse payload"
            continue
        results[event.event_uid] = _check_from_cache(
            rp, facts, versions, nodes, perms, comments,
        )
    return results


# ── Private collision checks (individual DB lookups) ──


async def _check_withdraw(db: AsyncSession, rp: dict) -> str | None:
    version_uid = rp.get("version_uid")
    if not version_uid:
        return "Missing version_uid in reverse payload"
    version = await db.get(FcFactVersion, UUID(version_uid))
    if not version:
        return "Version no longer exists"
    if version.state != "proposed":
        return f"Version state changed to {version.state}"
    return None


async def _check_unretire(db: AsyncSession, rp: dict) -> str | None:
    fact = await db.get(FcFact, UUID(rp["fact_uid"]))
    if not fact:
        return "Fact no longer exists"
    if not fact.is_retired:
        return "Fact is no longer retired — state has changed"
    return None


async def _check_retire(db: AsyncSession, rp: dict) -> str | None:
    fact = await db.get(FcFact, UUID(rp["fact_uid"]))
    if not fact:
        return "Fact no longer exists"
    if fact.is_retired:
        return "Fact is already retired — state has changed"
    return None


async def _check_restore_version(db: AsyncSession, rp: dict) -> str | None:
    prev_uid = rp.get("previous_version_uid")
    if not prev_uid:
        return "No previous version to restore"
    fact = await db.get(FcFact, UUID(rp["fact_uid"]))
    if not fact:
        return "Fact no longer exists"
    prev = await db.get(FcFactVersion, UUID(prev_uid))
    if not prev:
        return "Previous version no longer exists"
    return None


async def _check_reject_move(db: AsyncSession, rp: dict) -> str | None:
    """Check if a move proposal can still be rejected (cancelled)."""
    event_uid = rp.get("event_uid")
    if not event_uid:
        return "Missing event_uid in reverse payload"
    event = await db.get(FcEventLog, UUID(event_uid))
    if not event:
        return "Move proposal no longer exists"
    if event.event_type != "move.proposed":
        return f"Move is no longer pending — status is {event.event_type}"
    return None


async def _check_move_legacy(db: AsyncSession, rp: dict) -> str | None:
    """Backward compat: old format {"action":"move","fact_uid":...,"target_node_uid":...}."""
    fact_uid = rp.get("fact_uid") or rp.get("entity_uid")
    if fact_uid:
        fact = await db.get(FcFact, UUID(fact_uid))
        if not fact:
            return "Fact no longer exists"
    target = rp.get("target_node_uid")
    if target:
        node = await db.get(FcNode, UUID(target))
        if not node:
            return "Target node no longer exists"
        if node.is_archived:
            return "Target node is archived"
    return None


async def _check_move_back(db: AsyncSession, rp: dict) -> str | None:
    entity_type = rp.get("entity_type", "fact")
    entity_uid = UUID(rp["entity_uid"])
    if entity_type == "node":
        node = await db.get(FcNode, entity_uid)
        if not node:
            return "Node no longer exists"
    else:
        fact = await db.get(FcFact, entity_uid)
        if not fact:
            return "Fact no longer exists"
    original_node = await db.get(FcNode, UUID(rp["original_node_uid"]))
    if not original_node:
        return "Original node no longer exists"
    if original_node.is_archived:
        return "Original node is archived"
    return None


async def _check_unreject(db: AsyncSession, rp: dict) -> str | None:
    version = await db.get(FcFactVersion, UUID(rp["version_uid"]))
    if not version:
        return "Version no longer exists"
    if version.state != "rejected":
        return "Version is no longer rejected — state has changed"
    return None


async def _check_archive_node(db: AsyncSession, rp: dict) -> str | None:
    node = await db.get(FcNode, UUID(rp["node_uid"]))
    if not node:
        return "Node no longer exists"
    if node.is_archived:
        return "Node is already archived — state has changed"
    stmt = (
        select(FcFact.fact_uid)
        .where(FcFact.node_uid == node.node_uid, FcFact.is_retired.is_(False))
        .limit(1)
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        return "Node has active facts — cannot archive"
    return None


async def _check_unarchive_node(db: AsyncSession, rp: dict) -> str | None:
    node = await db.get(FcNode, UUID(rp["node_uid"]))
    if not node:
        return "Node no longer exists"
    if not node.is_archived:
        return "Node is not archived — state has changed"
    return None


async def _check_revoke_grant(db: AsyncSession, rp: dict) -> str | None:
    perm = await db.get(FcNodePermission, UUID(rp["permission_uid"]))
    if not perm:
        return "Permission not found"
    if perm.revoked_at is not None:
        return "Permission already revoked"
    return None


async def _check_restore_grant(db: AsyncSession, rp: dict) -> str | None:
    perm = await db.get(FcNodePermission, UUID(rp["permission_uid"]))
    if not perm:
        return "Permission not found"
    if perm.revoked_at is None:
        return "Permission is still active — state has changed"
    return None


async def _check_delete_comment(db: AsyncSession, rp: dict) -> str | None:
    comment = await db.get(FcFactComment, UUID(rp["comment_uid"]))
    if not comment:
        return "Comment no longer exists"
    return None


# ── Bulk fetch helpers ──


async def _bulk_fetch_facts(
    db: AsyncSession, uids: set[UUID],
) -> dict[UUID, FcFact]:
    stmt = select(FcFact).where(FcFact.fact_uid.in_(uids))
    result = await db.execute(stmt)
    return {f.fact_uid: f for f in result.scalars().all()}


async def _bulk_fetch_versions(
    db: AsyncSession, uids: set[UUID],
) -> dict[UUID, FcFactVersion]:
    stmt = select(FcFactVersion).where(FcFactVersion.version_uid.in_(uids))
    result = await db.execute(stmt)
    return {v.version_uid: v for v in result.scalars().all()}


async def _bulk_fetch_nodes(
    db: AsyncSession, uids: set[UUID],
) -> dict[UUID, FcNode]:
    stmt = select(FcNode).where(FcNode.node_uid.in_(uids))
    result = await db.execute(stmt)
    return {n.node_uid: n for n in result.scalars().all()}


async def _bulk_fetch_permissions(
    db: AsyncSession, uids: set[UUID],
) -> dict[UUID, FcNodePermission]:
    stmt = select(FcNodePermission).where(FcNodePermission.permission_uid.in_(uids))
    result = await db.execute(stmt)
    return {p.permission_uid: p for p in result.scalars().all()}


async def _bulk_fetch_comments(
    db: AsyncSession, uids: set[UUID],
) -> dict[UUID, FcFactComment]:
    stmt = select(FcFactComment).where(FcFactComment.comment_uid.in_(uids))
    result = await db.execute(stmt)
    return {c.comment_uid: c for c in result.scalars().all()}


def _check_from_cache(
    rp: dict,
    facts: dict[UUID, FcFact],
    versions: dict[UUID, FcFactVersion],
    nodes: dict[UUID, FcNode],
    perms: dict[UUID, FcNodePermission],
    comments: dict[UUID, FcFactComment],
) -> str | None:
    """Check collision using pre-fetched entity data."""
    action = rp.get("action", "")

    if action == "withdraw":
        uid = rp.get("version_uid")
        if not uid:
            return "Missing version_uid"
        v = versions.get(UUID(uid))
        if not v:
            return "Version no longer exists"
        if v.state != "proposed":
            return f"Version state changed to {v.state}"
        return None

    if action == "unretire":
        f = facts.get(UUID(rp["fact_uid"]))
        if not f:
            return "Fact no longer exists"
        if not f.is_retired:
            return "Fact is no longer retired — state has changed"
        return None

    if action == "retire":
        f = facts.get(UUID(rp["fact_uid"]))
        if not f:
            return "Fact no longer exists"
        if f.is_retired:
            return "Fact is already retired — state has changed"
        return None

    if action == "restore_version":
        f = facts.get(UUID(rp["fact_uid"]))
        if not f:
            return "Fact no longer exists"
        prev_uid = rp.get("previous_version_uid")
        if not prev_uid:
            return "No previous version to restore"
        if UUID(prev_uid) not in versions:
            return "Previous version no longer exists"
        return None

    if action == "move_back":
        entity_uid = UUID(rp["entity_uid"])
        entity_type = rp.get("entity_type", "fact")
        if entity_type == "node":
            if entity_uid not in nodes:
                return "Node no longer exists"
        else:
            if entity_uid not in facts:
                return "Fact no longer exists"
        orig_uid = UUID(rp["original_node_uid"])
        orig = nodes.get(orig_uid)
        if not orig:
            return "Original node no longer exists"
        if orig.is_archived:
            return "Original node is archived"
        return None

    if action == "move":
        # Backward compat: old format {"action":"move","fact_uid":...,"target_node_uid":...}
        fact_uid = rp.get("fact_uid") or rp.get("entity_uid")
        if fact_uid:
            if UUID(fact_uid) not in facts:
                return "Fact no longer exists"
        target = rp.get("target_node_uid")
        if target:
            t = nodes.get(UUID(target))
            if not t:
                return "Target node no longer exists"
            if t.is_archived:
                return "Target node is archived"
        return None

    if action == "reject_move":
        # Can't batch-check this efficiently — return None (safe) and let
        # the individual check handle it at undo time
        return None

    if action == "unreject":
        v = versions.get(UUID(rp["version_uid"]))
        if not v:
            return "Version no longer exists"
        if v.state != "rejected":
            return "Version is no longer rejected — state has changed"
        return None

    if action == "archive_node":
        n = nodes.get(UUID(rp["node_uid"]))
        if not n:
            return "Node no longer exists"
        if n.is_archived:
            return "Node is already archived — state has changed"
        # Note: active-fact check requires a DB query not done in batch
        return None

    if action == "unarchive_node":
        n = nodes.get(UUID(rp["node_uid"]))
        if not n:
            return "Node no longer exists"
        if not n.is_archived:
            return "Node is not archived — state has changed"
        return None

    if action == "revoke_grant":
        p = perms.get(UUID(rp["permission_uid"]))
        if not p:
            return "Permission not found"
        if p.revoked_at is not None:
            return "Permission already revoked"
        return None

    if action == "restore_grant":
        p = perms.get(UUID(rp["permission_uid"]))
        if not p:
            return "Permission not found"
        if p.revoked_at is None:
            return "Permission is still active — state has changed"
        return None

    if action == "delete_comment":
        c = comments.get(UUID(rp["comment_uid"]))
        if not c:
            return "Comment no longer exists"
        return None

    return f"Unknown undo action: {action}"
