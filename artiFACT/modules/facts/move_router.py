"""Move API endpoints for facts and nodes."""

import uuid
from typing import Any

from fastapi import APIRouter, Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.auth.session import get_session_data, is_auto_approve_active
from artiFACT.kernel.db import get_db
from artiFACT.kernel.models import FcUser
from artiFACT.modules.audit.service import flush_pending_events
from artiFACT.modules.facts.move_schemas import (
    MoveResultOut,
    PendingMoveOut,
    ProposeFactMove,
    ProposeNodeMove,
    RejectMoveRequest,
)
from artiFACT.modules.facts.move_service import (
    approve_move,
    get_pending_moves,
    propose_fact_move,
    propose_node_move,
    reject_move,
    reject_move_fact,
)
from artiFACT.modules.queue.scope_resolver import get_approvable_nodes

router = APIRouter(prefix="/api/v1/moves", tags=["moves"])


@router.post("/fact")
async def propose_fact(
    body: ProposeFactMove,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
    session_id: str | None = Cookie(None, alias="session_id"),
) -> MoveResultOut:
    """Propose (or auto-execute) moving a fact to a different node."""
    session_data = await get_session_data(session_id) if session_id else None
    auto = body.auto_approve and is_auto_approve_active(session_data)
    result = await propose_fact_move(
        db, body.fact_uid, body.target_node_uid, body.comment, user,
        auto_approve=auto,
    )
    await flush_pending_events(db)
    await db.commit()
    return MoveResultOut(**result)


@router.post("/node")
async def propose_node(
    body: ProposeNodeMove,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
    session_id: str | None = Cookie(None, alias="session_id"),
) -> MoveResultOut:
    """Propose (or auto-execute) moving a node subtree under a new parent."""
    session_data = await get_session_data(session_id) if session_id else None
    auto = body.auto_approve and is_auto_approve_active(session_data)
    result = await propose_node_move(
        db, body.node_uid, body.target_parent_uid, body.comment, user,
        auto_approve=auto,
    )
    await flush_pending_events(db)
    await db.commit()
    return MoveResultOut(**result)


@router.post("/{event_uid}/approve")
async def approve(
    event_uid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> MoveResultOut:
    """Approve a pending move proposal."""
    result = await approve_move(db, event_uid, user)
    await flush_pending_events(db)
    await db.commit()
    return MoveResultOut(**result)


@router.post("/{event_uid}/reject")
async def reject(
    event_uid: uuid.UUID,
    body: RejectMoveRequest = RejectMoveRequest(),
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> MoveResultOut:
    """Reject an entire move proposal."""
    result = await reject_move(db, event_uid, user, note=body.note)
    await flush_pending_events(db)
    await db.commit()
    return MoveResultOut(**result)


@router.post("/{event_uid}/reject-fact")
async def reject_single_fact(
    event_uid: uuid.UUID,
    body: RejectMoveRequest = RejectMoveRequest(),
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> MoveResultOut:
    """Reject a single fact within a node subtree move."""
    result = await reject_move_fact(db, event_uid, user, note=body.note)
    await flush_pending_events(db)
    await db.commit()
    return MoveResultOut(**result)


@router.get("/pending")
async def list_pending(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Return pending moves in user's approval scope with resolved names."""
    from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcUser as UserModel

    approvable = await get_approvable_nodes(db, user)
    moves = await get_pending_moves(db, list(approvable.keys()))

    data = []
    for m in moves:
        out = PendingMoveOut(**m)
        payload = out.payload or {}
        # Resolve fact sentence
        if out.entity_type == "fact":
            fact = await db.get(FcFact, out.entity_uid)
            if fact and fact.current_published_version_uid:
                ver = await db.get(FcFactVersion, fact.current_published_version_uid)
                if ver:
                    out.display_sentence = ver.display_sentence or ""
        # Resolve source/target node titles
        src_uid = payload.get("source_node_uid")
        tgt_uid = payload.get("target_node_uid")
        if src_uid:
            src = await db.get(FcNode, src_uid)
            if src:
                out.source_node_title = src.title
        if tgt_uid:
            tgt = await db.get(FcNode, tgt_uid)
            if tgt:
                out.target_node_title = tgt.title
        # Resolve actor name
        if out.actor_uid:
            actor = await db.get(UserModel, out.actor_uid)
            if actor:
                out.actor_name = actor.display_name
        out.comment = payload.get("comment", "")
        data.append(out.model_dump(mode="json"))
    return {"data": data, "total": len(data)}
