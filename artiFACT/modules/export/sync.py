"""Full dump + delta feed endpoints for Advana/Jupiter sync."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import (
    FcDocumentTemplate,
    FcEventLog,
    FcFact,
    FcFactVersion,
    FcNode,
    FcSignature,
    FcUser,
)


def _serialize_uuid(val: object) -> str | None:
    if val is None:
        return None
    return str(val)


def _serialize_dt(val: object) -> str | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)


async def _load_entity_snapshot(
    db: AsyncSession, entity_type: str, entity_uid: uuid.UUID
) -> dict:
    """Load current snapshot of an entity for the delta feed."""
    if entity_type == "fact":
        fact = await db.get(FcFact, entity_uid)
        if not fact:
            return {"entity_uid": str(entity_uid), "deleted": True}
        snapshot: dict = {
            "fact_uid": _serialize_uuid(fact.fact_uid),
            "node_uid": _serialize_uuid(fact.node_uid),
            "is_retired": fact.is_retired,
            "created_at": _serialize_dt(fact.created_at),
        }
        if fact.current_published_version_uid:
            ver = await db.get(FcFactVersion, fact.current_published_version_uid)
            if ver:
                snapshot.update({
                    "sentence": ver.display_sentence,
                    "state": ver.state,
                    "classification": ver.classification,
                    "published_at": _serialize_dt(ver.published_at),
                })
        return snapshot

    if entity_type == "node":
        node = await db.get(FcNode, entity_uid)
        if not node:
            return {"entity_uid": str(entity_uid), "deleted": True}
        return {
            "node_uid": _serialize_uuid(node.node_uid),
            "parent_node_uid": _serialize_uuid(node.parent_node_uid),
            "title": node.title,
            "slug": node.slug,
            "node_depth": node.node_depth,
            "is_archived": node.is_archived,
        }

    if entity_type == "signature":
        sig = await db.get(FcSignature, entity_uid)
        if not sig:
            return {"entity_uid": str(entity_uid), "deleted": True}
        return {
            "signature_uid": _serialize_uuid(sig.signature_uid),
            "node_uid": _serialize_uuid(sig.node_uid),
            "signed_by_uid": _serialize_uuid(sig.signed_by_uid),
            "signed_at": _serialize_dt(sig.signed_at),
            "fact_count": sig.fact_count,
        }

    if entity_type == "version":
        ver = await db.get(FcFactVersion, entity_uid)
        if not ver:
            return {"entity_uid": str(entity_uid), "deleted": True}
        return {
            "version_uid": _serialize_uuid(ver.version_uid),
            "fact_uid": _serialize_uuid(ver.fact_uid),
            "state": ver.state,
            "sentence": ver.display_sentence,
            "classification": ver.classification,
        }

    return {"entity_uid": str(entity_uid), "entity_type": entity_type}


async def get_delta_feed(
    db: AsyncSession, cursor: int = 0, limit: int = 500
) -> dict:
    """Return changes since cursor, ordered by monotonic seq."""
    stmt = (
        select(FcEventLog)
        .where(FcEventLog.seq > cursor)
        .order_by(FcEventLog.seq.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    events = list(result.scalars().all())

    changes = []
    for event in events:
        snapshot = await _load_entity_snapshot(db, event.entity_type, event.entity_uid)
        changes.append({
            "seq": event.seq,
            "occurred_at": _serialize_dt(event.occurred_at),
            "change_type": event.event_type,
            "entity_type": event.entity_type,
            "entity_uid": _serialize_uuid(event.entity_uid),
            "snapshot": snapshot,
        })

    max_seq = events[-1].seq if events else cursor
    return {
        "changes": changes,
        "cursor": max_seq,
        "has_more": len(events) == limit,
    }


async def get_full_dump(db: AsyncSession) -> dict:
    """Return complete data dump of all entities."""
    now = datetime.now(timezone.utc)

    # Nodes
    nodes_result = await db.execute(select(FcNode).order_by(FcNode.node_depth, FcNode.sort_order))
    nodes = [
        {
            "node_uid": _serialize_uuid(n.node_uid),
            "parent_node_uid": _serialize_uuid(n.parent_node_uid),
            "title": n.title,
            "slug": n.slug,
            "node_depth": n.node_depth,
            "sort_order": n.sort_order,
            "is_archived": n.is_archived,
            "created_at": _serialize_dt(n.created_at),
        }
        for n in nodes_result.scalars().all()
    ]

    # Facts
    facts_result = await db.execute(select(FcFact))
    facts = [
        {
            "fact_uid": _serialize_uuid(f.fact_uid),
            "node_uid": _serialize_uuid(f.node_uid),
            "is_retired": f.is_retired,
            "created_at": _serialize_dt(f.created_at),
        }
        for f in facts_result.scalars().all()
    ]

    # Versions
    versions_result = await db.execute(select(FcFactVersion))
    versions = [
        {
            "version_uid": _serialize_uuid(v.version_uid),
            "fact_uid": _serialize_uuid(v.fact_uid),
            "state": v.state,
            "sentence": v.display_sentence,
            "classification": v.classification,
            "created_at": _serialize_dt(v.created_at),
        }
        for v in versions_result.scalars().all()
    ]

    # Signatures
    sigs_result = await db.execute(select(FcSignature))
    signatures = [
        {
            "signature_uid": _serialize_uuid(s.signature_uid),
            "node_uid": _serialize_uuid(s.node_uid),
            "signed_by_uid": _serialize_uuid(s.signed_by_uid),
            "signed_at": _serialize_dt(s.signed_at),
            "fact_count": s.fact_count,
        }
        for s in sigs_result.scalars().all()
    ]

    # Users (display_name + role only, minimal PII)
    users_result = await db.execute(select(FcUser))
    users = [
        {
            "user_uid": _serialize_uuid(u.user_uid),
            "display_name": u.display_name,
            "global_role": u.global_role,
        }
        for u in users_result.scalars().all()
    ]

    # Templates
    tpls_result = await db.execute(select(FcDocumentTemplate))
    templates = [
        {
            "template_uid": _serialize_uuid(t.template_uid),
            "name": t.name,
            "abbreviation": t.abbreviation,
            "sections": t.sections,
            "is_active": t.is_active,
        }
        for t in tpls_result.scalars().all()
    ]

    # Events
    events_result = await db.execute(select(FcEventLog).order_by(FcEventLog.seq.asc()))
    events = [
        {
            "seq": e.seq,
            "event_type": e.event_type,
            "entity_type": e.entity_type,
            "entity_uid": _serialize_uuid(e.entity_uid),
            "occurred_at": _serialize_dt(e.occurred_at),
        }
        for e in events_result.scalars().all()
    ]

    # Current max seq for cursor
    max_seq_result = await db.execute(select(func.max(FcEventLog.seq)))
    max_seq = max_seq_result.scalar() or 0

    return {
        "exported_at": now.isoformat(),
        "schema_version": "2.0",
        "nodes": nodes,
        "facts": facts,
        "versions": versions,
        "signatures": signatures,
        "users": users,
        "templates": templates,
        "events": events,
        "cursor": max_seq,
    }
