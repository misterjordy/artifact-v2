"""Query and group user's undo actions for the undo pane."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import (
    FcEventLog,
    FcFact,
    FcFactVersion,
    FcNode,
    FcNodePermission,
    FcUser,
)
from artiFACT.modules.audit.collision_checker import batch_check_collisions
from artiFACT.modules.audit.schemas import UndoActionLine

log = structlog.get_logger()

BULK_THRESHOLD = 5
BULK_WINDOW_SECONDS = 30


async def get_undo_actions(
    db: AsyncSession, actor: FcUser, *, days: int = 30,
) -> list[UndoActionLine]:
    """Fetch the user's recent events and return grouped undo action lines."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = (
        select(FcEventLog)
        .where(
            FcEventLog.actor_uid == str(actor.user_uid),
            FcEventLog.occurred_at >= cutoff,
            FcEventLog.event_type != "undo",
        )
        .order_by(FcEventLog.occurred_at.desc())
    )
    result = await db.execute(stmt)
    events = list(result.scalars().all())

    if not events:
        return []

    # Batch collision check
    collision_map = await batch_check_collisions(db, events)

    # Pre-fetch entity details for descriptions
    details_map = await _fetch_entity_details(db, events)

    # Build action lines with descriptions
    raw_pairs = _build_raw_lines(events, collision_map, details_map)

    # Group into bulk lines (extract just the UndoActionLine part)
    return _group_into_undo_lines([p[0] for p in raw_pairs])


async def get_undo_actions_for_template(
    db: AsyncSession,
    actor: FcUser,
    *,
    days: int = 30,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return template-friendly dicts with bulk_items and total count.

    Fetches all events in the window, groups them, then applies offset/limit
    to the grouped result to support pagination.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = (
        select(FcEventLog)
        .where(
            FcEventLog.actor_uid == str(actor.user_uid),
            FcEventLog.occurred_at >= cutoff,
            FcEventLog.event_type != "undo",
        )
        .order_by(FcEventLog.occurred_at.desc())
    )
    result = await db.execute(stmt)
    events = list(result.scalars().all())

    if not events:
        return [], 0

    collision_map = await batch_check_collisions(db, events)
    details_map = await _fetch_entity_details(db, events)
    raw_pairs = _build_raw_lines(events, collision_map, details_map)

    all_grouped = _group_for_template(raw_pairs)
    total = len(all_grouped)
    page = all_grouped[offset:offset + limit]
    return page, total


def _line_to_dict(line: UndoActionLine, event: FcEventLog | None = None) -> dict:
    """Convert UndoActionLine to a template-friendly dict with string UUIDs."""
    payload = event.payload if event else {}
    payload = payload or {}

    # Resolve the fact_uid for onclick navigation
    fact_uid = ""
    if event:
        if event.entity_type == "fact":
            fact_uid = str(event.entity_uid)
        elif payload.get("fact_uid"):
            fact_uid = str(payload["fact_uid"])
        elif payload.get("entity_uid") and event.entity_type != "node":
            fact_uid = str(payload["entity_uid"])

    return {
        "event_uid": str(line.event_uid),
        "event_type": line.event_type,
        "description": line.description,
        "entity_detail": line.entity_detail,
        "context": line.context,
        "occurred_at": line.occurred_at,
        "is_undoable": line.is_undoable,
        "lock_reason": line.lock_reason,
        "is_bulk": line.is_bulk,
        "bulk_count": line.bulk_count,
        "bulk_event_uids": [str(u) for u in line.bulk_event_uids],
        "bulk_items": [],
        "fact_uid": fact_uid,
        "entity_type": event.entity_type if event else "",
    }


def _group_for_template(
    pairs: list[tuple[UndoActionLine, FcEventLog]],
) -> list[dict]:
    """Group lines and return template-friendly dicts with bulk_items."""
    if not pairs:
        return []

    groups: list[list[tuple[UndoActionLine, FcEventLog]]] = []
    current_group: list[tuple[UndoActionLine, FcEventLog]] = [pairs[0]]

    for i in range(1, len(pairs)):
        prev_line = current_group[-1][0]
        curr_line = pairs[i][0]
        gap = abs((prev_line.occurred_at - curr_line.occurred_at).total_seconds())
        if curr_line.event_type == prev_line.event_type and gap <= BULK_WINDOW_SECONDS:
            current_group.append(pairs[i])
        else:
            groups.append(current_group)
            current_group = [pairs[i]]
    groups.append(current_group)

    result: list[dict] = []
    for group in groups:
        if len(group) >= BULK_THRESHOLD:
            lines_only = [p[0] for p in group]
            bulk = _make_bulk_line(lines_only)
            d = _line_to_dict(bulk, group[0][1])
            d["bulk_items"] = [_line_to_dict(ln, ev) for ln, ev in group]
            result.append(d)
        else:
            for ln, ev in group:
                result.append(_line_to_dict(ln, ev))
    return result


def _build_raw_lines(
    events: list[FcEventLog],
    collision_map: dict[UUID, str | None],
    details_map: dict[str, str],
) -> list[tuple[UndoActionLine, FcEventLog]]:
    """Convert events to (UndoActionLine, original_event) pairs."""
    lines: list[tuple[UndoActionLine, FcEventLog]] = []
    for event in events:
        desc, entity_detail, context = describe_event(event, details_map)
        lock_reason = collision_map.get(event.event_uid)
        is_undoable = event.reversible and lock_reason is None
        if not event.reversible and lock_reason is None:
            lock_reason = "This action is not reversible"
        line = UndoActionLine(
            event_uid=event.event_uid,
            event_type=event.event_type,
            description=desc,
            entity_detail=entity_detail,
            context=context,
            occurred_at=event.occurred_at,
            is_undoable=is_undoable,
            lock_reason=lock_reason,
        )
        lines.append((line, event))
    return lines


def describe_event(
    event: FcEventLog, details_map: dict[str, str],
) -> tuple[str, str, dict[str, Any] | None]:
    """Return (description, entity_detail, context) for an event."""
    payload = event.payload or {}
    etype = event.event_type

    entity_detail = _get_detail(event, details_map)

    if etype == "fact.created":
        return "Proposed fact", entity_detail, None
    if etype == "fact.edited":
        ctx = None
        old_sentence = payload.get("old_sentence")
        new_sentence = payload.get("sentence")
        if old_sentence and new_sentence:
            ctx = {"old": old_sentence, "new": new_sentence}
        return "Edited fact", entity_detail, ctx
    if etype == "fact.retired":
        return "Retired fact", entity_detail, None
    if etype == "fact.unretired":
        return "Unretired fact", entity_detail, None
    if etype == "fact.moved":
        ctx = _move_context(payload, details_map)
        return "Moved fact", entity_detail, ctx
    if etype == "move.approved":
        ctx = _move_context(payload, details_map)
        if payload.get("comment"):
            ctx = ctx or {}
            ctx["comment"] = payload["comment"]
        return "Moved fact", entity_detail, ctx
    if etype == "move.proposed":
        ctx = _move_context(payload, details_map)
        if payload.get("comment"):
            ctx = ctx or {}
            ctx["comment"] = payload["comment"]
        return "Proposed move", entity_detail, ctx
    if etype == "move.rejected":
        return "Rejected move", entity_detail, None
    if etype in ("version.published", "fact.published"):
        return "Published fact", entity_detail, None
    if etype == "version.rejected":
        return "Rejected proposal", entity_detail, None
    if etype == "version.signed":
        return "Signed fact", entity_detail, None
    if etype == "node.created":
        return "Created node", entity_detail, None
    if etype == "node.archived":
        return "Archived node", entity_detail, None
    if etype == "grant.created":
        return "Granted permission", entity_detail, None
    if etype == "grant.revoked":
        return "Revoked permission", entity_detail, None
    if etype == "comment.created":
        # Get comment body: first from payload, then from DB via details_map
        body = payload.get("body", "")
        if not body:
            body = details_map.get(f"comment_body:{event.entity_uid}", "")
        # For comments, entity_detail should be the fact sentence (from version)
        version_uid = payload.get("version_uid")
        fact_detail = ""
        if version_uid:
            fact_detail = details_map.get(f"version:{version_uid}", "")
        return "Commented", fact_detail or entity_detail, {"comment_body": body}
    if etype == "signature.created":
        return "Signed", entity_detail, None
    if etype.startswith("challenge."):
        return f"Challenge {etype.split('.')[-1]}", entity_detail, None

    return etype, entity_detail, None


def _get_detail(event: FcEventLog, details_map: dict[str, str]) -> str:
    """Get human-readable entity detail from pre-fetched map."""
    key = f"{event.entity_type}:{event.entity_uid}"
    if key in details_map:
        return details_map[key]
    payload = event.payload or {}
    return payload.get("sentence", payload.get("title", ""))


def _move_context(
    payload: dict, details_map: dict[str, str],
) -> dict[str, str] | None:
    """Build from/to context for move events."""
    source = payload.get("source_node_uid") or payload.get("old_node_uid")
    target = payload.get("target_node_uid") or payload.get("new_node_uid")
    if source and target:
        from_name = details_map.get(f"node:{source}", str(source))
        to_name = details_map.get(f"node:{target}", str(target))
        return {"from": from_name, "to": to_name}
    return None


async def _fetch_entity_details(
    db: AsyncSession, events: list[FcEventLog],
) -> dict[str, str]:
    """Pre-fetch entity names/sentences for all events in one pass."""
    fact_uids: set[UUID] = set()
    version_uids: set[UUID] = set()
    node_uids: set[UUID] = set()
    perm_uids: set[UUID] = set()
    comment_uids: set[UUID] = set()

    for event in events:
        uid = event.entity_uid
        if event.entity_type == "fact":
            fact_uids.add(uid)
        elif event.entity_type == "version":
            version_uids.add(uid)
        elif event.entity_type == "node":
            node_uids.add(uid)
        elif event.entity_type == "permission":
            perm_uids.add(uid)
        elif event.entity_type == "comment":
            comment_uids.add(uid)
        # Collect node UIDs from payload for move context
        payload = event.payload or {}
        for key in ("source_node_uid", "target_node_uid", "old_node_uid", "new_node_uid"):
            val = payload.get(key)
            if val:
                node_uids.add(UUID(val))
        # Collect version UIDs from comment payloads for fact sentence lookup
        if payload.get("version_uid"):
            version_uids.add(UUID(payload["version_uid"]))

    details: dict[str, str] = {}

    if fact_uids:
        stmt = select(FcFact).where(FcFact.fact_uid.in_(fact_uids))
        result = await db.execute(stmt)
        for fact in result.scalars().all():
            # Get current version sentence
            if fact.current_published_version_uid:
                version_uids.add(fact.current_published_version_uid)
            details[f"fact:{fact.fact_uid}"] = ""

    if version_uids:
        stmt = select(FcFactVersion).where(FcFactVersion.version_uid.in_(version_uids))
        result = await db.execute(stmt)
        for v in result.scalars().all():
            details[f"version:{v.version_uid}"] = v.display_sentence or ""
            details[f"fact:{v.fact_uid}"] = v.display_sentence or ""

    if node_uids:
        stmt = select(FcNode).where(FcNode.node_uid.in_(node_uids))
        result = await db.execute(stmt)
        for n in result.scalars().all():
            details[f"node:{n.node_uid}"] = n.title

    if perm_uids:
        stmt = select(FcNodePermission).where(
            FcNodePermission.permission_uid.in_(perm_uids),
        )
        result = await db.execute(stmt)
        for p in result.scalars().all():
            node_title = details.get(f"node:{p.node_uid}", "")
            details[f"permission:{p.permission_uid}"] = f"{p.role} on {node_title}"

    if comment_uids:
        from artiFACT.kernel.models import FcFactComment
        stmt = select(FcFactComment).where(FcFactComment.comment_uid.in_(comment_uids))
        result = await db.execute(stmt)
        for c in result.scalars().all():
            details[f"comment_body:{c.comment_uid}"] = c.body or ""

    return details


def _group_into_undo_lines(
    lines: list[UndoActionLine],
) -> list[UndoActionLine]:
    """Group consecutive same-type events within 30s into bulk lines.

    Lines are already sorted by occurred_at DESC (newest first).
    Groups of 5+ become single bulk lines; groups <5 stay individual.
    """
    if not lines:
        return []

    groups: list[list[UndoActionLine]] = []
    current_group: list[UndoActionLine] = [lines[0]]

    for i in range(1, len(lines)):
        prev = current_group[-1]
        curr = lines[i]
        gap = abs((prev.occurred_at - curr.occurred_at).total_seconds())
        if curr.event_type == prev.event_type and gap <= BULK_WINDOW_SECONDS:
            current_group.append(curr)
        else:
            groups.append(current_group)
            current_group = [curr]
    groups.append(current_group)

    result: list[UndoActionLine] = []
    for group in groups:
        if len(group) >= BULK_THRESHOLD:
            result.append(_make_bulk_line(group))
        else:
            result.extend(group)
    return result


def _make_bulk_line(group: list[UndoActionLine]) -> UndoActionLine:
    """Collapse a group of 5+ events into a single bulk undo line."""
    first = group[0]
    all_uids = [line.event_uid for line in group]
    all_undoable = all(line.is_undoable for line in group)
    lock_reason = next(
        (line.lock_reason for line in group if line.lock_reason), None,
    )
    desc = f"{first.description} ({len(group)} items)"

    return UndoActionLine(
        event_uid=first.event_uid,
        event_type=first.event_type,
        description=desc,
        entity_detail=first.entity_detail,
        context=first.context,
        occurred_at=first.occurred_at,
        is_undoable=all_undoable,
        lock_reason=lock_reason,
        is_bulk=True,
        bulk_count=len(group),
        bulk_event_uids=all_uids,
    )
