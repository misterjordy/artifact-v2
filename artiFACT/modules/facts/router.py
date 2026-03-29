"""Facts API endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.db import get_db
from artiFACT.kernel.models import FcFact, FcFactVersion, FcUser
from artiFACT.modules.audit.service import flush_pending_events
from artiFACT.modules.facts.bulk import bulk_move, bulk_retire
from artiFACT.modules.facts.reassign import reassign_fact
from artiFACT.modules.facts.schemas import (
    BulkMoveRequest,
    BulkRetireRequest,
    FactCreate,
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
) -> dict:
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
) -> dict:
    """Return version history for a fact."""
    versions = await get_fact_versions(db, fact_uid)
    data = [VersionOut.model_validate(v) for v in versions]
    return {"data": [d.model_dump(mode="json") for d in data], "total": len(data)}


@router.post("/facts", status_code=201)
async def create(
    body: FactCreate,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> FactWithVersionOut:
    """Create a new fact with its initial version."""
    fact, version = await create_fact(
        db,
        body.node_uid,
        body.sentence,
        user,
        metadata_tags=body.metadata_tags,
        source_reference=body.source_reference,
        effective_date=body.effective_date,
        classification=body.classification,
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
) -> FactWithVersionOut:
    """Edit a fact (creates a new version superseding the current one)."""
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
) -> dict:
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
) -> dict:
    """Move multiple facts. All-or-nothing."""
    moved = await bulk_move(db, body.fact_uids, body.target_node_uid, user)
    await flush_pending_events(db)
    await db.commit()
    return {"moved": [str(uid) for uid in moved]}
