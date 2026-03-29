"""Import pipeline API endpoints."""

import json
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.db import get_db
from artiFACT.kernel.exceptions import NotFound
from artiFACT.kernel.models import FcImportSession, FcUser
from artiFACT.kernel.rate_limiter import check_rate
from artiFACT.modules.import_pipeline.schemas import (
    ProposeOut,
    ProposeRequest,
    RecommendLocationOut,
    RecommendLocationRequest,
    SessionOut,
    StagedFact,
    StagedFactsOut,
)
from artiFACT.modules.import_pipeline.upload_handler import handle_upload

router = APIRouter(prefix="/api/v1/import", tags=["import_pipeline"])


@router.post("/upload", response_model=SessionOut, status_code=201)
async def upload_document(
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
    await db.commit()
    return SessionOut.model_validate(session)


@router.post("/analyze/{session_uid}")
async def trigger_analysis(
    session_uid: UUID,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
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

    async def event_stream():
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
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


@router.get("/sessions/{session_uid}/staged", response_model=StagedFactsOut)
async def get_staged_facts(
    session_uid: UUID,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StagedFactsOut:
    """Get staged facts for review."""
    session = await db.get(FcImportSession, session_uid)
    if not session:
        raise NotFound("Import session not found", code="SESSION_NOT_FOUND")
    if not session.staged_facts_s3:
        raise NotFound("No staged facts available", code="NO_STAGED_FACTS")

    from artiFACT.modules.import_pipeline.stager import load_staged_facts

    staged = load_staged_facts(session.staged_facts_s3)
    facts = [StagedFact(**f) for f in staged]

    return StagedFactsOut(
        session_uid=session_uid,
        facts=facts,
        total=len(facts),
    )


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
) -> dict:
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
