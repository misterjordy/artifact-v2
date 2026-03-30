"""Queue API endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.db import get_db
from artiFACT.kernel.models import FcUser
from artiFACT.modules.audit.service import flush_pending_events
from artiFACT.modules.queue.badge_counter import get_badge_count
from artiFACT.modules.queue.proposal_query import get_move_proposals, get_proposals, get_unsigned
from artiFACT.modules.queue.revision import revise_and_publish
from artiFACT.modules.queue.challenge_service import (
    approve_challenge,
    get_my_challenges,
    get_pending_challenges,
    reject_challenge,
)
from artiFACT.modules.queue.schemas import (
    ApproveRequest,
    BadgeCountOut,
    ChallengeOut,
    ChallengeRejectRequest,
    MoveProposalOut,
    MyChallengeOut,
    ProposalOut,
    RejectRequest,
    ReviseRequest,
)
from artiFACT.modules.queue.scope_resolver import get_approvable_nodes
from artiFACT.modules.queue.service import (
    approve_move,
    approve_proposal,
    reject_move,
    reject_proposal,
)

router = APIRouter(prefix="/api/v1/queue", tags=["queue"])


@router.get("/proposals")
async def list_proposals(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Pending proposals for current user's scope."""
    approvable = await get_approvable_nodes(db, user)
    rows = await get_proposals(db, list(approvable.keys()))
    data = [ProposalOut(**row).model_dump(mode="json") for row in rows]
    return {"data": data, "total": len(data)}


@router.get("/moves")
async def list_moves(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Pending move proposals."""
    approvable = await get_approvable_nodes(db, user)
    rows = await get_move_proposals(db, list(approvable.keys()))
    data = [MoveProposalOut(**row).model_dump(mode="json") for row in rows]
    return {"data": data, "total": len(data)}


@router.get("/unsigned")
async def list_unsigned(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Facts awaiting signature."""
    approvable = await get_approvable_nodes(db, user)
    rows = await get_unsigned(db, list(approvable.keys()))
    data = [ProposalOut(**row).model_dump(mode="json") for row in rows]
    return {"data": data, "total": len(data)}


@router.get("/challenges")
async def list_challenges(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Pending challenges for current user's approval scope."""
    approvable = await get_approvable_nodes(db, user)
    rows = await get_pending_challenges(db, list(approvable.keys()))
    data = [ChallengeOut(**row).model_dump(mode="json") for row in rows]
    return {"data": data, "total": len(data)}


@router.get("/my-challenges")
async def list_my_challenges(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Challenges submitted by the current user (notification view)."""
    rows = await get_my_challenges(db, user.user_uid)
    data = [MyChallengeOut(**row).model_dump(mode="json") for row in rows]
    return {"data": data, "total": len(data)}


@router.get("/counts")
async def badge_counts(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> BadgeCountOut:
    """Badge counts (cached in Redis)."""
    approvable = await get_approvable_nodes(db, user)
    node_uids = list(approvable.keys())
    proposals_count = await get_badge_count(db, user.user_uid, node_uids)
    moves = await get_move_proposals(db, node_uids)
    challenges = await get_pending_challenges(db, node_uids)
    return BadgeCountOut(
        proposals=proposals_count,
        moves=len(moves),
        challenges=len(challenges),
        total=proposals_count + len(moves) + len(challenges),
    )


@router.post("/approve/{version_uid}")
async def approve(
    version_uid: uuid.UUID,
    body: ApproveRequest = ApproveRequest(),
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Approve a proposed version."""
    version = await approve_proposal(db, version_uid, user, note=body.note)
    await flush_pending_events(db)
    await db.commit()
    return {"status": "approved", "version_uid": str(version.version_uid)}


@router.post("/reject/{version_uid}")
async def reject(
    version_uid: uuid.UUID,
    body: RejectRequest = RejectRequest(),
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Reject a proposed version."""
    version = await reject_proposal(db, version_uid, user, note=body.note)
    await flush_pending_events(db)
    await db.commit()
    return {"status": "rejected", "version_uid": str(version.version_uid)}


@router.post("/revise/{version_uid}")
async def revise(
    version_uid: uuid.UUID,
    body: ReviseRequest,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Revise language: reject original + publish revised (atomic)."""
    revised = await revise_and_publish(db, version_uid, body.revised_sentence, user, note=body.note)
    await flush_pending_events(db)
    await db.commit()
    return {"status": "revised", "version_uid": str(revised.version_uid)}


@router.post("/approve-move/{event_uid}")
async def approve_move_endpoint(
    event_uid: uuid.UUID,
    body: ApproveRequest = ApproveRequest(),
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Approve a move proposal."""
    fact = await approve_move(db, event_uid, user, note=body.note)
    await flush_pending_events(db)
    await db.commit()
    return {"status": "move_approved", "fact_uid": str(fact.fact_uid)}


@router.post("/reject-move/{event_uid}")
async def reject_move_endpoint(
    event_uid: uuid.UUID,
    body: RejectRequest = RejectRequest(),
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Reject a move proposal."""
    await reject_move(db, event_uid, user, note=body.note)
    await flush_pending_events(db)
    await db.commit()
    return {"status": "move_rejected"}


@router.post("/approve-challenge/{comment_uid}")
async def approve_challenge_endpoint(
    comment_uid: uuid.UUID,
    body: ApproveRequest = ApproveRequest(),
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Approve a challenge: create new published version with the proposed sentence."""
    comment = await approve_challenge(db, comment_uid, user, note=body.note)
    await flush_pending_events(db)
    await db.commit()
    return {"status": "challenge_approved", "comment_uid": str(comment.comment_uid)}


@router.post("/reject-challenge/{comment_uid}")
async def reject_challenge_endpoint(
    comment_uid: uuid.UUID,
    body: ChallengeRejectRequest = ChallengeRejectRequest(),
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Reject a challenge with optional note."""
    comment = await reject_challenge(db, comment_uid, user, note=body.note)
    await flush_pending_events(db)
    await db.commit()
    return {"status": "challenge_rejected", "comment_uid": str(comment.comment_uid)}
