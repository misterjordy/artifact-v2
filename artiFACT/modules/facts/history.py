"""Service functions for fact version history and comments."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.events import publish
from artiFACT.kernel.exceptions import Conflict, Forbidden, NotFound
from artiFACT.kernel.models import (
    FcEventLog,
    FcFact,
    FcFactComment,
    FcFactVersion,
    FcUser,
)
from artiFACT.kernel.permissions.resolver import can

VALID_COMMENT_TYPES = {"comment", "challenge", "resolution"}
CHALLENGE_WINDOW_DAYS = 30


def _user_dict(user: FcUser) -> dict[str, Any]:
    """Build a serialisable author dict from an FcUser row."""
    return {
        "user_uid": str(user.user_uid),
        "display_name": user.display_name,
        "username": user.cac_dn,
    }


async def _load_user_map(
    db: AsyncSession, user_uids: set[UUID],
) -> dict[UUID, FcUser]:
    """Batch-load users by uid."""
    if not user_uids:
        return {}
    stmt = select(FcUser).where(FcUser.user_uid.in_(user_uids))
    result = await db.execute(stmt)
    return {u.user_uid: u for u in result.scalars().all()}


async def get_fact_history(
    db: AsyncSession, fact_uid: UUID, user: FcUser,
) -> dict[str, Any]:
    """Return enriched version history for a fact (batch, no N+1)."""
    fact = await db.get(FcFact, fact_uid)
    if not fact:
        raise NotFound("Fact not found", code="FACT_NOT_FOUND")

    if not await can(user, "read", fact.node_uid, db):
        raise Forbidden("Cannot view this fact", code="FORBIDDEN")

    # 1. All versions for this fact, ordered newest-first via supersedes chain
    ver_stmt = (
        select(FcFactVersion)
        .where(FcFactVersion.fact_uid == fact_uid)
        .order_by(FcFactVersion.created_at.desc())
    )
    raw_versions = list((await db.execute(ver_stmt)).scalars().all())
    versions = _order_by_supersedes_chain(raw_versions)
    version_uids = [v.version_uid for v in versions]

    # 2. Batch comments
    comments_by_version: dict[UUID, list[FcFactComment]] = {uid: [] for uid in version_uids}
    if version_uids:
        c_stmt = (
            select(FcFactComment)
            .where(FcFactComment.version_uid.in_(version_uids))
            .order_by(FcFactComment.created_at.asc())
        )
        for c in (await db.execute(c_stmt)).scalars().all():
            comments_by_version[c.version_uid].append(c)

    # 3. Batch events (version events + move events for this fact)
    events_by_version: dict[UUID, list[FcEventLog]] = {uid: [] for uid in version_uids}
    move_events: list[FcEventLog] = []
    if version_uids:
        e_stmt = (
            select(FcEventLog)
            .where(
                FcEventLog.entity_uid.in_(version_uids),
                FcEventLog.entity_type == "version",
            )
            .order_by(FcEventLog.occurred_at.asc())
        )
        for e in (await db.execute(e_stmt)).scalars().all():
            events_by_version[e.entity_uid].append(e)

    # Move events for this fact
    move_stmt = (
        select(FcEventLog)
        .where(
            FcEventLog.entity_type == "fact",
            FcEventLog.entity_uid == fact_uid,
            FcEventLog.event_type.in_(["move.proposed", "move.approved", "move.rejected"]),
        )
        .order_by(FcEventLog.occurred_at.asc())
    )
    move_events = list((await db.execute(move_stmt)).scalars().all())

    # 4. Batch-load all referenced users
    user_uids: set[UUID] = set()
    for v in versions:
        if v.created_by_uid:
            user_uids.add(v.created_by_uid)
    for clist in comments_by_version.values():
        for c in clist:
            if c.created_by_uid:
                user_uids.add(c.created_by_uid)
            if c.resolved_by_uid:
                user_uids.add(c.resolved_by_uid)
    for elist in events_by_version.values():
        for e in elist:
            if e.actor_uid:
                user_uids.add(e.actor_uid)
    for me in move_events:
        if me.actor_uid:
            user_uids.add(me.actor_uid)
    user_map = await _load_user_map(db, user_uids)

    unknown = {"user_uid": "", "display_name": "Unknown", "username": "unknown"}

    # 5. Determine current sentence
    current_sentence = _resolve_current_sentence(fact, versions)

    # 6. Assemble
    now = datetime.now(timezone.utc)
    challenge_cutoff = now - timedelta(days=CHALLENGE_WINDOW_DAYS)

    version_dicts = []
    for v in versions:
        author = user_map.get(v.created_by_uid, None) if v.created_by_uid else None
        # A version is challengeable if published/rejected/proposed within the last 30 days
        pub_ts = v.published_at or v.created_at
        challengeable = (
            v.state in ("published", "rejected", "proposed")
            and pub_ts >= challenge_cutoff
        )
        version_dicts.append({
            "version_uid": v.version_uid,
            "state": v.state,
            "display_sentence": v.display_sentence,
            "change_summary": v.change_summary,
            "created_by": _user_dict(author) if author else unknown,
            "created_at": v.created_at,
            "published_at": v.published_at,
            "signed_at": v.signed_at,
            "effective_date": v.effective_date,
            "classification": v.classification,
            "is_current_published": v.version_uid == fact.current_published_version_uid,
            "is_current_signed": v.version_uid == fact.current_signed_version_uid,
            "challengeable": challengeable,
            "comments": _build_comments(comments_by_version[v.version_uid], user_map, unknown),
            "events": _build_events(events_by_version[v.version_uid], user_map, unknown),
        })

    move_dicts = _build_move_events(move_events, user_map, unknown)

    return {
        "fact_uid": fact.fact_uid,
        "node_uid": fact.node_uid,
        "current_sentence": current_sentence,
        "is_retired": fact.is_retired,
        "versions": version_dicts,
        "move_events": move_dicts,
    }


def _order_by_supersedes_chain(versions: list[FcFactVersion]) -> list[FcFactVersion]:
    """Order versions newest-first using supersedes_version_uid chain.

    Walk from the chain tip (versions that nothing supersedes) backward.
    Falls back to created_at DESC for versions outside the chain (e.g.,
    competing proposals that all supersede the same published version).
    """
    if len(versions) <= 1:
        return versions

    by_uid = {v.version_uid: v for v in versions}
    # Find which version_uids are superseded by something
    superseded: set[UUID] = set()
    for v in versions:
        if v.supersedes_version_uid and v.supersedes_version_uid in by_uid:
            superseded.add(v.supersedes_version_uid)

    # Tips: versions that are NOT superseded by any other version in this set
    tips = [v for v in versions if v.version_uid not in superseded]
    # Sort tips newest-first by created_at as tiebreaker
    tips.sort(key=lambda v: v.created_at, reverse=True)

    # Walk each tip down the chain
    ordered: list[FcFactVersion] = []
    seen: set[UUID] = set()
    for tip in tips:
        current: FcFactVersion | None = tip
        while current and current.version_uid not in seen:
            ordered.append(current)
            seen.add(current.version_uid)
            current = by_uid.get(current.supersedes_version_uid) if current.supersedes_version_uid else None

    # Append any orphans not reached by chain walking
    for v in versions:
        if v.version_uid not in seen:
            ordered.append(v)

    return ordered


def _resolve_current_sentence(
    fact: FcFact, versions: list[FcFactVersion],
) -> str:
    """Pick the best display sentence for the pane title."""
    if fact.current_published_version_uid:
        for v in versions:
            if v.version_uid == fact.current_published_version_uid:
                return v.display_sentence
    return versions[0].display_sentence if versions else ""


def _build_comments(
    comments: list[FcFactComment],
    user_map: dict[UUID, FcUser],
    unknown: dict[str, str],
) -> list[dict[str, Any]]:
    """Serialise a list of comments."""
    out = []
    for c in comments:
        author = user_map.get(c.created_by_uid) if c.created_by_uid else None
        resolver = user_map.get(c.resolved_by_uid) if c.resolved_by_uid else None
        out.append({
            "comment_uid": c.comment_uid,
            "version_uid": c.version_uid,
            "parent_comment_uid": c.parent_comment_uid,
            "comment_type": c.comment_type,
            "body": c.body,
            "created_by": _user_dict(author) if author else unknown,
            "created_at": c.created_at,
            "proposed_sentence": c.proposed_sentence,
            "resolution_state": c.resolution_state,
            "resolution_note": c.resolution_note,
            "resolved_at": c.resolved_at,
            "resolved_by": _user_dict(resolver) if resolver else None,
        })
    return out


def _build_events(
    events: list[FcEventLog],
    user_map: dict[UUID, FcUser],
    unknown: dict[str, str],
) -> list[dict[str, Any]]:
    """Serialise a list of audit events.

    The rejection note may live in FcEventLog.note (top-level column) OR
    in payload["note"] (when emitted by queue/service.py's reject_proposal,
    which publishes a second version.rejected event with the note in payload
    but not the column). Check both locations.
    """
    out = []
    for e in events:
        actor = user_map.get(e.actor_uid) if e.actor_uid else None
        note = e.note
        if not note and e.payload and isinstance(e.payload, dict):
            note = e.payload.get("note")
        out.append({
            "event_uid": e.event_uid,
            "event_type": e.event_type,
            "actor": _user_dict(actor) if actor else unknown,
            "occurred_at": e.occurred_at,
            "note": note,
        })
    return out


def _build_move_events(
    events: list[FcEventLog],
    user_map: dict[UUID, FcUser],
    unknown: dict[str, str],
) -> list[dict[str, Any]]:
    """Serialise move events for fact history."""
    out = []
    for e in events:
        actor = user_map.get(e.actor_uid) if e.actor_uid else None
        payload = e.payload or {}
        out.append({
            "event_uid": e.event_uid,
            "event_type": e.event_type,
            "actor": _user_dict(actor) if actor else unknown,
            "occurred_at": e.occurred_at,
            "source_node_uid": payload.get("source_node_uid"),
            "target_node_uid": payload.get("target_node_uid"),
            "comment": payload.get("comment"),
            "correlation_id": payload.get("correlation_id"),
            "note": e.note or payload.get("note"),
        })
    return out


async def add_comment(
    db: AsyncSession,
    fact_uid: UUID,
    version_uid: UUID,
    body: str,
    comment_type: str,
    parent_comment_uid: UUID | None,
    user: FcUser,
    *,
    proposed_sentence: str | None = None,
) -> FcFactComment:
    """Add a comment to a specific version of a fact.

    When comment_type is "challenge", a proposed_sentence is required and
    the target version must be the current published version.
    """
    body = body.strip()
    if not body:
        raise Conflict("Comment body cannot be empty", code="EMPTY_BODY")

    if comment_type not in VALID_COMMENT_TYPES:
        raise Conflict(f"Invalid comment_type: {comment_type}", code="INVALID_TYPE")

    if comment_type == "challenge":
        if not proposed_sentence or not proposed_sentence.strip():
            raise Conflict(
                "Challenge must include a proposed sentence",
                code="CHALLENGE_MISSING_SENTENCE",
            )
        proposed_sentence = proposed_sentence.strip()

    fact = await db.get(FcFact, fact_uid)
    if not fact:
        raise NotFound("Fact not found", code="FACT_NOT_FOUND")

    if not await can(user, "contribute", fact.node_uid, db):
        raise Forbidden("Cannot comment on facts in this node", code="FORBIDDEN")

    version = await db.get(FcFactVersion, version_uid)
    if not version or version.fact_uid != fact_uid:
        raise NotFound("Version not found for this fact", code="VERSION_NOT_FOUND")

    if comment_type == "challenge" and version.state not in ("published", "rejected", "proposed"):
        raise Conflict(
            "Can only challenge a published, rejected, or proposed version",
            code="CHALLENGE_NOT_CHALLENGEABLE",
        )

    if comment_type == "challenge":
        pub_ts = version.published_at or version.created_at
        cutoff = datetime.now(timezone.utc) - timedelta(days=CHALLENGE_WINDOW_DAYS)
        if pub_ts < cutoff:
            raise Conflict(
                "Challenge window has closed (older than 30 days)",
                code="CHALLENGE_WINDOW_CLOSED",
            )

    if parent_comment_uid:
        parent = await db.get(FcFactComment, parent_comment_uid)
        if not parent:
            raise NotFound("Parent comment not found", code="PARENT_NOT_FOUND")
        if parent.version_uid != version_uid:
            raise Conflict(
                "Parent comment belongs to a different version",
                code="PARENT_VERSION_MISMATCH",
            )

    comment = FcFactComment(
        version_uid=version_uid,
        parent_comment_uid=parent_comment_uid,
        comment_type=comment_type,
        body=body,
        created_by_uid=user.user_uid,
        proposed_sentence=proposed_sentence if comment_type == "challenge" else None,
    )
    db.add(comment)
    await db.flush()

    event_type = "challenge.created" if comment_type == "challenge" else "comment.created"
    await publish(
        event_type,
        {
            "comment_uid": str(comment.comment_uid),
            "version_uid": str(version_uid),
            "fact_uid": str(fact_uid),
            "actor_uid": str(user.user_uid),
            "comment_type": comment_type,
        },
    )

    return comment
