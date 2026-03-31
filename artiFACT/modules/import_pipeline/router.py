"""Import pipeline API endpoints."""

import hashlib
import json
from collections.abc import AsyncIterator
from datetime import date
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.auth.session import update_session_field
from artiFACT.kernel.db import get_db
from artiFACT.kernel.exceptions import Forbidden, NotFound
from artiFACT.kernel.models import FcImportSession, FcImportStagedFact, FcUser
from artiFACT.kernel.permissions.resolver import can
from artiFACT.kernel.rate_limiter import check_rate
from artiFACT.modules.import_pipeline.schemas import (
    PasteImportRequest,
    ProposeOut,
    ProposeRequest,
    RecommendLocationOut,
    RecommendLocationRequest,
    SessionOut,
    StagedFact,
    StagedFactOut,
    StagedFactUpdate,
    StagedFactsOut,
)
from artiFACT.modules.import_pipeline.upload_handler import handle_upload

log = structlog.get_logger()

router = APIRouter(prefix="/api/v1/import", tags=["import_pipeline"])


@router.post("/upload", response_model=SessionOut, status_code=201)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    program_node_uid: UUID = Form(...),
    effective_date: date = Form(...),
    granularity: str = Form("standard"),
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionOut:
    """Upload a document for import processing."""
    await check_rate(str(user.user_uid), "api_write")

    session = await handle_upload(
        db=db,
        file=file,
        program_node_uid=program_node_uid,
        effective_date=effective_date,
        actor=user,
        granularity=granularity,
    )

    await _force_auto_approve_off(request)

    await db.commit()
    return SessionOut.model_validate(session)


@router.post("/paste", status_code=201)
async def paste_import(
    request: Request,
    body: PasteImportRequest,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create import session from pasted text and trigger analysis."""
    await check_rate(str(user.user_uid), "api_write")

    if not await can(user, "contribute", body.program_node_uid, db):
        raise Forbidden("Cannot import into this node", code="FORBIDDEN")

    text_hash = hashlib.sha256(body.text.encode()).hexdigest()

    session = FcImportSession(
        program_node_uid=body.program_node_uid,
        source_filename="paste.txt",
        source_hash=text_hash,
        effective_date=body.effective_date,
        granularity=body.granularity,
        input_type="text",
        source_text=body.text,
        constraint_node_uids=(
            [str(u) for u in body.constraint_node_uids] if body.constraint_node_uids else None
        ),
        created_by_uid=user.user_uid,
    )
    db.add(session)
    await db.flush()

    await _force_auto_approve_off(request)

    await db.commit()

    from artiFACT.modules.import_pipeline.analyzer import analyze_document

    analyze_document.delay(str(session.session_uid))

    return {"session_uid": str(session.session_uid), "status": "analyzing"}


@router.post("/analyze/{session_uid}")
async def trigger_analysis(
    session_uid: UUID,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Trigger AI extraction as a background Celery task."""
    await check_rate(str(user.user_uid), "api_write")

    session = await db.get(FcImportSession, session_uid)
    if not session:
        raise NotFound("Import session not found", code="SESSION_NOT_FOUND")

    from artiFACT.modules.import_pipeline.analyzer import analyze_document

    analyze_document.delay(str(session_uid))

    return {"status": "analyzing", "session_uid": str(session_uid)}


@router.get("/sessions/{session_uid}", response_model=SessionOut)
async def get_session(
    session_uid: UUID,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionOut:
    """Get import session status."""
    session = await db.get(FcImportSession, session_uid)
    if not session:
        raise NotFound("Import session not found", code="SESSION_NOT_FOUND")
    return SessionOut.model_validate(session)


@router.get("/sessions/{session_uid}/progress")
async def stream_progress(
    session_uid: UUID,
    user: FcUser = Depends(get_current_user),
) -> StreamingResponse:
    """SSE endpoint for real-time progress updates."""
    import redis.asyncio as aioredis
    from artiFACT.kernel.config import settings

    async def event_stream() -> AsyncIterator[str]:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)  # type: ignore[no-untyped-call]
        pubsub = r.pubsub()
        await pubsub.subscribe(f"import:{session_uid}")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
                    data = json.loads(message["data"])
                    if data.get("percent", 0) >= 100 or data.get("percent", 0) < 0:
                        break
        finally:
            await pubsub.unsubscribe(f"import:{session_uid}")
            await r.aclose()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/sessions/{session_uid}/staged")
async def get_staged_facts(
    session_uid: UUID,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get staged facts for review (from Postgres), with existing sentences for dups/conflicts."""
    from artiFACT.kernel.models import FcFactVersion, FcNode

    session = await db.get(FcImportSession, session_uid)
    if not session:
        raise NotFound("Import session not found", code="SESSION_NOT_FOUND")

    from artiFACT.modules.import_pipeline.stager import load_staged_facts_postgres

    staged = await load_staged_facts_postgres(db, session_uid)
    if not staged:
        raise NotFound("No staged facts available", code="NO_STAGED_FACTS")

    # Collect version UIDs that need existing sentence lookup
    version_uids = set()
    for sf in staged:
        if sf.duplicate_of_uid:
            version_uids.add(sf.duplicate_of_uid)
        if sf.conflict_with_uid:
            version_uids.add(sf.conflict_with_uid)

    existing_sentences: dict[str, str] = {}
    if version_uids:
        rows = (await db.execute(
            select(FcFactVersion.version_uid, FcFactVersion.display_sentence)
            .where(FcFactVersion.version_uid.in_(list(version_uids)))
        )).all()
        existing_sentences = {str(r[0]): r[1] for r in rows}

    # Collect node UIDs for title lookup
    node_uids = {sf.suggested_node_uid for sf in staged if sf.suggested_node_uid}
    node_titles: dict[str, str] = {}
    if node_uids:
        rows = (await db.execute(
            select(FcNode.node_uid, FcNode.title).where(FcNode.node_uid.in_(list(node_uids)))
        )).all()
        node_titles = {str(r[0]): r[1] for r in rows}

    facts = []
    for sf in staged:
        d = StagedFactOut.model_validate(sf).model_dump()
        # Add existing sentence for resolution modal
        dup_uid = str(sf.duplicate_of_uid) if sf.duplicate_of_uid else None
        conf_uid = str(sf.conflict_with_uid) if sf.conflict_with_uid else None
        d["existing_sentence"] = existing_sentences.get(dup_uid or conf_uid or "", None)
        d["node_title"] = node_titles.get(str(sf.suggested_node_uid), None) if sf.suggested_node_uid else None
        facts.append(d)

    return {"session_uid": str(session_uid), "facts": facts, "total": len(facts)}


@router.patch("/staged/{staged_fact_uid}")
async def update_staged_fact(
    staged_fact_uid: UUID,
    body: StagedFactUpdate,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update a single staged fact during review."""
    staged = await db.get(FcImportStagedFact, staged_fact_uid)
    if not staged:
        raise NotFound("Staged fact not found", code="STAGED_FACT_NOT_FOUND")

    if body.suggested_node_uid is not None:
        staged.suggested_node_uid = body.suggested_node_uid
    if body.display_sentence is not None:
        if not staged.original_sentence:
            staged.original_sentence = staged.display_sentence
        staged.display_sentence = body.display_sentence
    if body.status is not None:
        staged.status = body.status
    if body.resolution is not None:
        staged.resolution = body.resolution
        from sqlalchemy.sql import func

        staged.resolved_at = func.now()

    await db.commit()
    return {"status": "updated", "staged_fact_uid": str(staged_fact_uid)}


@router.get("/sessions/{session_uid}/download-unresolved")
async def download_unresolved(
    session_uid: UUID,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    """Download unresolved facts (duplicates, conflicts, orphaned) as .txt."""
    session = await db.get(FcImportSession, session_uid)
    if not session:
        raise NotFound("Import session not found", code="SESSION_NOT_FOUND")

    result = await db.execute(
        select(FcImportStagedFact)
        .where(
            FcImportStagedFact.session_uid == session_uid,
            FcImportStagedFact.status.in_(["duplicate", "conflict", "orphaned"]),
        )
        .order_by(FcImportStagedFact.source_chunk_index)
    )
    unresolved = result.scalars().all()

    lines = []
    for sf in unresolved:
        prefix = f"[{sf.status.upper()}]"
        lines.append(f"{prefix} {sf.display_sentence}")
        if sf.conflict_reason:
            lines.append(f"  Reason: {sf.conflict_reason}")

    body = "\n".join(lines) if lines else "No unresolved facts."
    filename = f"unresolved-{session.source_filename.rsplit('.', 1)[0]}.txt"
    return PlainTextResponse(
        content=body,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/sessions/{session_uid}/reset")
async def reset_session(
    session_uid: UUID,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Reset session: delete staged facts, S3 doc, set status=discarded."""
    session = await db.get(FcImportSession, session_uid)
    if not session:
        raise NotFound("Import session not found", code="SESSION_NOT_FOUND")

    from artiFACT.modules.import_pipeline.stager import delete_staged_facts

    await delete_staged_facts(db, session_uid)

    if session.source_s3_key:
        try:
            from artiFACT.kernel.s3 import delete_object

            delete_object(session.source_s3_key)
        except Exception:
            log.warning("s3_delete_failed", session_uid=str(session_uid))

    session.status = "discarded"
    await db.commit()
    return {"status": "reset"}


@router.post("/sessions/{session_uid}/rerun")
async def rerun_session(
    session_uid: UUID,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Re-run classification + conflict detection without re-extracting."""
    session = await db.get(FcImportSession, session_uid)
    if not session:
        raise NotFound("Import session not found", code="SESSION_NOT_FOUND")

    from artiFACT.modules.import_pipeline.analyzer import rerun_analysis

    rerun_analysis.delay(str(session_uid))

    return {"status": "analyzing"}


@router.post("/sessions/{session_uid}/propose", response_model=ProposeOut)
async def propose_staged(
    session_uid: UUID,
    body: ProposeRequest,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProposeOut:
    """Accept staged facts and create real facts (all-or-nothing transaction)."""
    from artiFACT.modules.import_pipeline.proposer import propose_facts

    created = await propose_facts(db, session_uid, body.accepted_indices, user)
    await db.commit()
    return ProposeOut(created_count=created, session_uid=session_uid)


@router.post("/sessions/{session_uid}/discard")
async def discard_staged(
    session_uid: UUID,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Discard staged facts."""
    session = await db.get(FcImportSession, session_uid)
    if not session:
        raise NotFound("Import session not found", code="SESSION_NOT_FOUND")

    session.status = "rejected"
    await db.commit()
    return {"status": "rejected", "session_uid": str(session_uid)}


@router.post("/recommend-location", response_model=RecommendLocationOut)
async def recommend_location(
    body: RecommendLocationRequest,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecommendLocationOut:
    """AI-powered node placement recommendation."""
    from artiFACT.modules.import_pipeline.location_recommender import recommend_locations

    recs = await recommend_locations(db, body.sentences, body.program_node_uid, user)
    return RecommendLocationOut(recommendations=recs)


async def _force_auto_approve_off(request: Request) -> None:
    """Force auto-approve off in the user's current session."""
    session_id = request.cookies.get("session_id")
    if session_id:
        await update_session_field(session_id, "auto_approve", False)
