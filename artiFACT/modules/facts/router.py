"""Facts API endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, Cookie, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.auth.session import get_session_data, is_auto_approve_active
from artiFACT.kernel.db import get_db
from artiFACT.kernel.models import FcFact, FcFactVersion, FcUser
from artiFACT.modules.audit.service import flush_pending_events
from artiFACT.modules.facts.bulk import bulk_move, bulk_retire
from artiFACT.modules.facts.reassign import reassign_fact
from artiFACT.modules.facts.history import add_comment, get_fact_history
from artiFACT.modules.facts.schemas import (
    BulkMoveRequest,
    BulkRetireRequest,
    CommentCreate,
    CommentOut,
    FactCreate,
    FactHistoryOut,
    FactMoveRequest,
    FactOut,
    FactUpdate,
    FactWithVersionOut,
    VersionOut,
)
from artiFACT.modules.facts.service import (
    create_fact,
    edit_fact,
    get_fact_versions,
    retire_fact,
    unretire_fact,
)

router = APIRouter(prefix="/api/v1", tags=["facts"])


@router.get("/facts")
async def list_facts(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
    node_uid: uuid.UUID | None = Query(None),
    state: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """List facts, optionally filtered by node and/or state."""
    stmt = select(FcFact).where(FcFact.is_retired.is_(False))
    if node_uid:
        stmt = stmt.where(FcFact.node_uid == node_uid)
    stmt = stmt.order_by(FcFact.created_at.desc())

    count_result = await db.execute(select(FcFact.fact_uid).where(FcFact.is_retired.is_(False)))
    total = len(count_result.all())

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    facts = result.scalars().all()

    data = []
    for fact in facts:
        fout = FactOut.model_validate(fact)
        version_out = None
        if fact.current_published_version_uid:
            ver = await db.get(FcFactVersion, fact.current_published_version_uid)
            if ver:
                version_out = VersionOut.model_validate(ver)
        data.append(
            FactWithVersionOut(
                **fout.model_dump(),
                current_version=version_out,
            )
        )

    return {
        "data": [d.model_dump(mode="json") for d in data],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/facts/{fact_uid}")
async def get_fact(
    fact_uid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> FactWithVersionOut:
    """Get a single fact with its current published version."""
    from artiFACT.kernel.exceptions import NotFound

    fact = await db.get(FcFact, fact_uid)
    if not fact:
        raise NotFound("Fact not found", code="FACT_NOT_FOUND")

    version_out = None
    if fact.current_published_version_uid:
        ver = await db.get(FcFactVersion, fact.current_published_version_uid)
        if ver:
            version_out = VersionOut.model_validate(ver)

    return FactWithVersionOut(
        **FactOut.model_validate(fact).model_dump(),
        current_version=version_out,
    )


@router.get("/facts/{fact_uid}/versions")
async def list_versions(
    fact_uid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Return version history for a fact."""
    versions = await get_fact_versions(db, fact_uid)
    data = [VersionOut.model_validate(v) for v in versions]
    return {"data": [d.model_dump(mode="json") for d in data], "total": len(data)}


@router.post("/facts", status_code=201)
async def create(
    body: FactCreate,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
    session_id: str | None = Cookie(None, alias="session_id"),
) -> FactWithVersionOut:
    """Create a new fact with its initial version."""
    session_data = await get_session_data(session_id) if session_id else None
    auto_approve = is_auto_approve_active(session_data)
    fact, version = await create_fact(
        db,
        body.node_uid,
        body.sentence,
        user,
        metadata_tags=body.metadata_tags,
        source_reference=body.source_reference,
        effective_date=body.effective_date,
        classification=body.classification,
        auto_approve=auto_approve,
    )
    await flush_pending_events(db)
    await db.commit()
    await db.refresh(fact)
    await db.refresh(version)

    return FactWithVersionOut(
        **FactOut.model_validate(fact).model_dump(),
        current_version=VersionOut.model_validate(version),
    )


@router.put("/facts/{fact_uid}")
async def update(
    fact_uid: uuid.UUID,
    body: FactUpdate,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
    session_id: str | None = Cookie(None, alias="session_id"),
) -> FactWithVersionOut:
    """Edit a fact (creates a new version superseding the current one)."""
    session_data = await get_session_data(session_id) if session_id else None
    auto_approve = is_auto_approve_active(session_data)
    fact, version = await edit_fact(
        db,
        fact_uid,
        body.sentence,
        user,
        metadata_tags=body.metadata_tags,
        source_reference=body.source_reference,
        effective_date=body.effective_date,
        classification=body.classification,
        change_summary=body.change_summary,
        auto_approve=auto_approve,
    )
    await flush_pending_events(db)
    await db.commit()
    await db.refresh(fact)
    await db.refresh(version)

    return FactWithVersionOut(
        **FactOut.model_validate(fact).model_dump(),
        current_version=VersionOut.model_validate(version),
    )


@router.post("/facts/{fact_uid}/retire")
async def retire(
    fact_uid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> FactOut:
    """Retire a fact (soft delete)."""
    fact = await retire_fact(db, fact_uid, user)
    await flush_pending_events(db)
    await db.commit()
    return FactOut.model_validate(fact)


@router.post("/facts/{fact_uid}/unretire")
async def unretire(
    fact_uid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> FactOut:
    """Unretire a previously retired fact."""
    fact = await unretire_fact(db, fact_uid, user)
    await flush_pending_events(db)
    await db.commit()
    return FactOut.model_validate(fact)


@router.post("/facts/{fact_uid}/move")
async def move(
    fact_uid: uuid.UUID,
    body: FactMoveRequest,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> FactOut:
    """Move a fact to a different node."""
    fact = await reassign_fact(db, fact_uid, body.target_node_uid, user)
    await flush_pending_events(db)
    await db.commit()
    return FactOut.model_validate(fact)


@router.post("/facts/bulk/retire")
async def bulk_retire_endpoint(
    body: BulkRetireRequest,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Retire multiple facts. All-or-nothing."""
    retired = await bulk_retire(db, body.fact_uids, user)
    await flush_pending_events(db)
    await db.commit()
    return {"retired": [str(uid) for uid in retired]}


@router.post("/facts/bulk/move")
async def bulk_move_endpoint(
    body: BulkMoveRequest,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Move multiple facts. All-or-nothing."""
    moved = await bulk_move(db, body.fact_uids, body.target_node_uid, user)
    await flush_pending_events(db)
    await db.commit()
    return {"moved": [str(uid) for uid in moved]}


@router.get("/facts/{fact_uid}/history")
async def fact_history(
    fact_uid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Return enriched version history for a fact."""
    data = await get_fact_history(db, fact_uid, user)
    return {"data": FactHistoryOut(**data).model_dump(mode="json")}


@router.post("/facts/{fact_uid}/versions/{version_uid}/comments", status_code=201)
async def create_comment(
    fact_uid: uuid.UUID,
    version_uid: uuid.UUID,
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Add a comment to a specific version of a fact."""
    comment = await add_comment(
        db, fact_uid, version_uid, body.body, body.comment_type,
        body.parent_comment_uid, user,
        proposed_sentence=body.proposed_sentence,
    )
    await flush_pending_events(db)
    await db.commit()
    await db.refresh(comment)
    author = await db.get(FcUser, comment.created_by_uid)
    out = CommentOut(
        comment_uid=comment.comment_uid,
        version_uid=comment.version_uid,
        parent_comment_uid=comment.parent_comment_uid,
        comment_type=comment.comment_type,
        body=comment.body,
        created_by={
            "user_uid": str(author.user_uid) if author else "",
            "display_name": author.display_name if author else "Unknown",
            "username": author.cac_dn if author else "unknown",
        },
        created_at=comment.created_at,
        proposed_sentence=comment.proposed_sentence,
        resolution_state=comment.resolution_state,
        resolution_note=comment.resolution_note,
        resolved_at=comment.resolved_at,
    )
    return {"data": out.model_dump(mode="json")}
