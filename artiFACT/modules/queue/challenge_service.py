"""Challenge approve/reject logic with scope enforcement."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.events import publish
from artiFACT.kernel.exceptions import Conflict, Forbidden, NotFound
from artiFACT.kernel.models import FcFact, FcFactComment, FcFactVersion, FcNode, FcUser
from artiFACT.modules.queue.scope_resolver import get_approvable_nodes


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def approve_challenge(
    db: AsyncSession,
    comment_uid: uuid.UUID,
    actor: FcUser,
    *,
    note: str | None = None,
) -> FcFactComment:
    """Approve a challenge: create new published version with the proposed sentence."""
    comment = await db.get(FcFactComment, comment_uid)
    if not comment or comment.comment_type != "challenge":
        raise NotFound("Challenge not found", code="CHALLENGE_NOT_FOUND")
    if comment.resolution_state is not None:
        raise Conflict("Challenge already resolved", code="CHALLENGE_ALREADY_RESOLVED")

    version = await db.get(FcFactVersion, comment.version_uid)
    if not version:
        raise NotFound("Version not found")
    fact = await db.get(FcFact, version.fact_uid)
    if not fact:
        raise NotFound("Fact not found")

    approvable = await get_approvable_nodes(db, actor)
    if fact.node_uid not in approvable:
        raise Forbidden("This fact is outside your approval scope")

    # Guard against approving a challenge whose target version has already been superseded
    if fact.current_published_version_uid != version.version_uid:
        raise Conflict(
            "This version has already been superseded",
            code="VERSION_SUPERSEDED",
        )

    async with db.begin_nested():
        new_version = FcFactVersion(
            fact_uid=fact.fact_uid,
            display_sentence=comment.proposed_sentence,
            metadata_tags=version.metadata_tags or [],
            source_reference=version.source_reference,
            effective_date=version.effective_date,
            classification=version.classification,
            change_summary=f"Challenge approved: {note}" if note else "Challenge approved",
            supersedes_version_uid=version.version_uid,
            created_by_uid=actor.user_uid,
            state="published",
            published_at=_utcnow(),
        )
        db.add(new_version)
        await db.flush()

        fact.current_published_version_uid = new_version.version_uid

        comment.resolution_state = "approved"
        comment.resolved_at = _utcnow()
        comment.resolved_by_uid = actor.user_uid

    await publish(
        "challenge.approved",
        {
            "comment_uid": str(comment.comment_uid),
            "version_uid": str(new_version.version_uid),
            "fact_uid": str(fact.fact_uid),
            "actor_uid": str(actor.user_uid),
            "challenger_uid": str(comment.created_by_uid),
        },
    )
    await publish(
        "version.published",
        {
            "version_uid": str(new_version.version_uid),
            "fact_uid": str(fact.fact_uid),
            "actor_uid": str(actor.user_uid),
            "old_state": "proposed",
            "new_state": "published",
        },
    )

    return comment


async def reject_challenge(
    db: AsyncSession,
    comment_uid: uuid.UUID,
    actor: FcUser,
    *,
    note: str | None = None,
) -> FcFactComment:
    """Reject a challenge: mark resolved with optional note."""
    comment = await db.get(FcFactComment, comment_uid)
    if not comment or comment.comment_type != "challenge":
        raise NotFound("Challenge not found", code="CHALLENGE_NOT_FOUND")
    if comment.resolution_state is not None:
        raise Conflict("Challenge already resolved", code="CHALLENGE_ALREADY_RESOLVED")

    version = await db.get(FcFactVersion, comment.version_uid)
    if not version:
        raise NotFound("Version not found")
    fact = await db.get(FcFact, version.fact_uid)
    if not fact:
        raise NotFound("Fact not found")

    approvable = await get_approvable_nodes(db, actor)
    if fact.node_uid not in approvable:
        raise Forbidden("This fact is outside your approval scope")

    async with db.begin_nested():
        comment.resolution_state = "rejected"
        comment.resolution_note = note
        comment.resolved_at = _utcnow()
        comment.resolved_by_uid = actor.user_uid

    await publish(
        "challenge.rejected",
        {
            "comment_uid": str(comment.comment_uid),
            "version_uid": str(version.version_uid),
            "fact_uid": str(fact.fact_uid),
            "actor_uid": str(actor.user_uid),
            "challenger_uid": str(comment.created_by_uid),
            "note": note,
        },
    )

    return comment


async def get_pending_challenges(
    db: AsyncSession,
    node_uids: list[uuid.UUID],
) -> list[dict]:
    """Return pending challenges in the given nodes for the approver queue."""
    if not node_uids:
        return []

    stmt = (
        select(FcFactComment, FcFactVersion, FcFact, FcNode, FcUser)
        .join(FcFactVersion, FcFactComment.version_uid == FcFactVersion.version_uid)
        .join(FcFact, FcFactVersion.fact_uid == FcFact.fact_uid)
        .join(FcNode, FcFact.node_uid == FcNode.node_uid)
        .outerjoin(FcUser, FcFactComment.created_by_uid == FcUser.user_uid)
        .where(
            FcFactComment.comment_type == "challenge",
            FcFactComment.resolution_state.is_(None),
            FcFact.node_uid.in_(node_uids),
        )
        .order_by(FcFactComment.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "comment_uid": c.comment_uid,
            "fact_uid": f.fact_uid,
            "version_uid": v.version_uid,
            "node_uid": n.node_uid,
            "node_title": n.title,
            "display_sentence": v.display_sentence,
            "proposed_sentence": c.proposed_sentence,
            "body": c.body,
            "created_by_uid": c.created_by_uid,
            "created_by_name": u.display_name if u else None,
            "created_at": c.created_at,
        }
        for c, v, f, n, u in rows
    ]


async def get_my_challenges(
    db: AsyncSession,
    user_uid: uuid.UUID,
) -> list[dict]:
    """Return challenges submitted by the given user (for notification view)."""
    stmt = (
        select(FcFactComment, FcFactVersion, FcFact, FcNode, FcUser)
        .join(FcFactVersion, FcFactComment.version_uid == FcFactVersion.version_uid)
        .join(FcFact, FcFactVersion.fact_uid == FcFact.fact_uid)
        .join(FcNode, FcFact.node_uid == FcNode.node_uid)
        .outerjoin(FcUser, FcFactComment.resolved_by_uid == FcUser.user_uid)
        .where(
            FcFactComment.comment_type == "challenge",
            FcFactComment.created_by_uid == user_uid,
        )
        .order_by(FcFactComment.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "comment_uid": c.comment_uid,
            "fact_uid": f.fact_uid,
            "node_title": n.title,
            "display_sentence": v.display_sentence,
            "proposed_sentence": c.proposed_sentence,
            "body": c.body,
            "resolution_state": c.resolution_state,
            "resolution_note": c.resolution_note,
            "resolved_at": c.resolved_at,
            "resolved_by_name": u.display_name if u else None,
            "created_at": c.created_at,
        }
        for c, v, f, n, u in rows
    ]
