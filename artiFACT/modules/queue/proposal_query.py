"""Query builders for the three queue panes."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcEventLog, FcFact, FcFactVersion, FcNode, FcUser


async def get_proposals(db: AsyncSession, node_uids: list[uuid.UUID]) -> list[dict[str, Any]]:
    """Pending proposed versions scoped to node_uids. One query with JOINs."""
    if not node_uids:
        return []

    stmt = (
        select(
            FcFactVersion.version_uid,
            FcFactVersion.fact_uid,
            FcFact.node_uid,
            FcNode.title.label("node_title"),
            FcFactVersion.display_sentence,
            FcFactVersion.state,
            FcFactVersion.classification,
            FcFactVersion.created_by_uid,
            FcUser.display_name.label("created_by_name"),
            FcFactVersion.created_at,
        )
        .join(FcFact, FcFactVersion.fact_uid == FcFact.fact_uid)
        .join(FcNode, FcFact.node_uid == FcNode.node_uid)
        .outerjoin(FcUser, FcFactVersion.created_by_uid == FcUser.user_uid)
        .where(
            FcFactVersion.state == "proposed",
            FcFact.node_uid.in_(node_uids),
            FcFact.is_retired.is_(False),
        )
        .order_by(FcFactVersion.created_at.asc())
    )
    result = await db.execute(stmt)
    return [row._asdict() for row in result.all()]


async def get_move_proposals(db: AsyncSession, node_uids: list[uuid.UUID]) -> list[dict[str, Any]]:
    """Pending move proposals from fc_event_log where target is in scope."""
    if not node_uids:
        return []

    stmt = (
        select(FcEventLog)
        .where(
            FcEventLog.event_type == "fact.move_proposed",
            FcEventLog.entity_type == "fact",
        )
        .order_by(FcEventLog.occurred_at.asc())
    )
    result = await db.execute(stmt)
    events = result.scalars().all()

    node_uid_set = set(node_uids)
    moves: list[dict[str, Any]] = []
    for event in events:
        payload = event.payload or {}
        target_uid_str = payload.get("target_node_uid")
        if not target_uid_str:
            continue
        target_uid = uuid.UUID(target_uid_str)
        if target_uid not in node_uid_set:
            continue

        fact_uid = uuid.UUID(payload["fact_uid"])
        fact = await db.get(FcFact, fact_uid)
        if not fact or fact.is_retired:
            continue

        source_node = await db.get(FcNode, fact.node_uid)
        target_node = await db.get(FcNode, target_uid)
        sentence = ""
        if fact.current_published_version_uid:
            ver = await db.get(FcFactVersion, fact.current_published_version_uid)
            if ver:
                sentence = ver.display_sentence

        actor = await db.get(FcUser, event.actor_uid) if event.actor_uid else None

        moves.append(
            {
                "event_uid": event.event_uid,
                "fact_uid": fact_uid,
                "display_sentence": sentence,
                "source_node_uid": fact.node_uid,
                "source_node_title": source_node.title if source_node else "",
                "target_node_uid": target_uid,
                "target_node_title": target_node.title if target_node else "",
                "actor_uid": event.actor_uid,
                "actor_name": actor.display_name if actor else None,
                "occurred_at": event.occurred_at,
            }
        )

    return moves


async def get_unsigned(db: AsyncSession, node_uids: list[uuid.UUID]) -> list[dict[str, Any]]:
    """Published but not yet signed versions in scope."""
    if not node_uids:
        return []

    stmt = (
        select(
            FcFactVersion.version_uid,
            FcFactVersion.fact_uid,
            FcFact.node_uid,
            FcNode.title.label("node_title"),
            FcFactVersion.display_sentence,
            FcFactVersion.state,
            FcFactVersion.classification,
            FcFactVersion.created_by_uid,
            FcUser.display_name.label("created_by_name"),
            FcFactVersion.created_at,
        )
        .join(FcFact, FcFactVersion.fact_uid == FcFact.fact_uid)
        .join(FcNode, FcFact.node_uid == FcNode.node_uid)
        .outerjoin(FcUser, FcFactVersion.created_by_uid == FcUser.user_uid)
        .where(
            FcFactVersion.state == "published",
            FcFact.node_uid.in_(node_uids),
            FcFact.is_retired.is_(False),
        )
        .order_by(FcFactVersion.created_at.asc())
    )
    result = await db.execute(stmt)
    return [row._asdict() for row in result.all()]
