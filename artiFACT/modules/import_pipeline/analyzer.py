"""AI-powered fact extraction (Celery task)."""

import asyncio
import json
import os
from typing import Any
from uuid import UUID

import redis as sync_redis
import structlog
from sqlalchemy import create_engine, select
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from artiFACT.kernel.ai_provider import AIProvider
from artiFACT.kernel.background import app as celery_app
from artiFACT.kernel.models import FcImportSession, FcImportStagedFact, FcUser
from artiFACT.kernel.s3 import download_bytes
from artiFACT.modules.import_pipeline.deduplicator import deduplicate, jaccard, tokenize
from artiFACT.modules.import_pipeline.extractors import get_extractor
from artiFACT.modules.import_pipeline.prompts import compute_max_facts, load_skill
from artiFACT.modules.import_pipeline.stager import stage_facts_postgres, stage_facts_s3

log = structlog.get_logger()

def _get_extraction_prompts() -> tuple[str, str]:
    """Load atomicfact skill prompts (cached after first call)."""
    return load_skill("atomicfact")

_SYNC_DB_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://artifact:artifact_dev@postgres:5432/artifact_db"
).replace("+asyncpg", "")
_sync_engine = create_engine(_SYNC_DB_URL, pool_pre_ping=True)

_redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
_redis_client = sync_redis.from_url(_redis_url, decode_responses=True)  # type: ignore[no-untyped-call]


def _publish_progress(session_uid: str, message: str, percent: float) -> None:
    """Publish progress event via Redis pub/sub."""
    payload = json.dumps({"message": message, "percent": percent})
    _redis_client.publish(f"import:{session_uid}", payload)


def _chunk_text(text: str, max_chars: int = 3000) -> list[str]:
    """Split text into chunks, preferring paragraph boundaries."""
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 > max_chars and current:
            chunks.append(current.strip())
            current = para
        else:
            current = current + "\n\n" + para if current else para
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text]


_ai = AIProvider()


def _parse_extracted_facts(response_text: str) -> list[dict[str, Any]]:
    """Parse AI response into list of fact dicts with 'sentence' key."""
    try:
        data = json.loads(response_text)
        raw = data.get("facts", [])
        results: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, str):
                results.append({"sentence": item, "metadata_tags": []})
            elif isinstance(item, dict):
                if "sentence" not in item and len(item) == 1:
                    # Handle {"fact": "text"} variants
                    item["sentence"] = next(iter(item.values()))
                results.append(item)
        return results
    except json.JSONDecodeError:
        return []


def _classify_sync(
    facts: list[str],
    db: Session,
    program_node_uid: UUID,
    user_uid: UUID,
    constraint_node_uids: list[str] | None = None,
) -> list[dict]:
    """Run async classifier from sync Celery task context."""
    from artiFACT.modules.import_pipeline.classifier import build_taxonomy_index, classify_all

    async def _run() -> list[dict]:
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        async_url = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://artifact:artifact_dev@postgres:5432/artifact_db",
        )
        engine = create_async_engine(async_url, pool_pre_ping=True)
        async with AsyncSession(engine) as async_db:
            taxonomy_text, id_mapping = await build_taxonomy_index(async_db, program_node_uid)
            return await classify_all(
                facts, taxonomy_text, id_mapping, async_db, user_uid, constraint_node_uids
            )

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


def _detect_conflicts_sync(
    staged_facts: list[FcImportStagedFact],
    existing_facts: list[tuple[str, UUID]],
    user_uid: UUID,
) -> list[dict]:
    """Run async conflict detector from sync Celery task context."""
    from artiFACT.modules.import_pipeline.conflict_detector import detect_conflicts

    async def _run() -> list[dict]:
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        async_url = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://artifact:artifact_dev@postgres:5432/artifact_db",
        )
        engine = create_async_engine(async_url, pool_pre_ping=True)
        async with AsyncSession(engine) as async_db:
            return await detect_conflicts(
                staged_facts, existing_facts, async_db, user_uid, jaccard, tokenize
            )

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


def _get_existing_facts(db: Session, program_node_uid: UUID) -> list[tuple[str, UUID]]:
    """Get current published version of each fact under a program node and all descendants."""
    rows = db.execute(
        sa_text(
            "WITH RECURSIVE tree AS ("
            "  SELECT node_uid FROM fc_node WHERE node_uid = :node_uid"
            "  UNION ALL"
            "  SELECT n.node_uid FROM fc_node n JOIN tree t ON n.parent_node_uid = t.node_uid"
            ") "
            "SELECT fv.display_sentence, fv.version_uid "
            "FROM fc_fact f "
            "JOIN tree t ON f.node_uid = t.node_uid "
            "JOIN fc_fact_version fv ON fv.version_uid = f.current_published_version_uid "
            "WHERE f.is_retired = false "
            "AND f.current_published_version_uid IS NOT NULL"
        ),
        {"node_uid": str(program_node_uid)},
    ).fetchall()
    return [(row[0], UUID(str(row[1]))) for row in rows]


def _extract_facts_from_document(
    session: FcImportSession,
    db: Session,
    user_uid: UUID,
    session_uid_str: str,
    granularity: str,
) -> list[dict[str, Any]]:
    """Extract facts from an uploaded document via S3."""
    if not session.source_s3_key:
        raise RuntimeError("No source S3 key")
    content = download_bytes(session.source_s3_key)

    extractor = get_extractor(session.source_filename)
    text = extractor.extract(content)
    _publish_progress(session_uid_str, "Extracted text", 10)

    chunks = _chunk_text(text)
    _publish_progress(session_uid_str, f"Split into {len(chunks)} chunks", 20)

    system_prompt, user_template = _get_extraction_prompts()

    all_facts: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunks):
        max_facts = compute_max_facts(chunk, granularity)
        user_msg = user_template.format(max_facts=max_facts, chunk_text=chunk)
        response = _ai.complete_sync(
            db, user_uid,
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_msg}],
            response_format={"type": "json_object"},
        )
        facts = _parse_extracted_facts(response)
        all_facts.extend(facts)
        pct = 10 + (70 * (i + 1) / len(chunks))
        _publish_progress(session_uid_str, f"Extracting atomic facts... chunk {i + 1}/{len(chunks)}", pct)

    return all_facts


def _extract_facts_from_text(
    source_text: str,
    db: Session,
    user_uid: UUID,
    session_uid_str: str,
    granularity: str,
) -> list[dict[str, Any]]:
    """Extract facts from pasted text (skip S3 + file extractor)."""
    _publish_progress(session_uid_str, "Processing pasted text", 10)

    chunks = _chunk_text(source_text)
    _publish_progress(session_uid_str, f"Split into {len(chunks)} chunks", 20)

    system_prompt, user_template = _get_extraction_prompts()

    all_facts: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunks):
        max_facts = compute_max_facts(chunk, granularity)
        user_msg = user_template.format(max_facts=max_facts, chunk_text=chunk)
        response = _ai.complete_sync(
            db, user_uid,
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_msg}],
            response_format={"type": "json_object"},
        )
        facts = _parse_extracted_facts(response)
        all_facts.extend(facts)
        pct = 10 + (70 * (i + 1) / len(chunks))
        _publish_progress(session_uid_str, f"Extracting atomic facts... chunk {i + 1}/{len(chunks)}", pct)

    return all_facts


@celery_app.task(name="import_pipeline.analyze_document")  # type: ignore[misc]
def analyze_document(session_uid_str: str) -> None:
    """Celery task: extract, classify, deduplicate, detect conflicts, stage."""
    with Session(_sync_engine) as db:
        session = db.get(FcImportSession, session_uid_str)
        if not session:
            return

        session.status = "analyzing"
        db.commit()

        try:
            _run_analysis(db, session, session_uid_str)
        except Exception as e:
            log.error("import_analysis_failed", session_uid=session_uid_str, error=str(e))
            session.status = "failed"
            session.error_message = str(e)
            _publish_progress(session_uid_str, f"Failed: {e}", -1)

        db.commit()


def _run_analysis(db: Session, session: FcImportSession, session_uid_str: str) -> None:
    """Core analysis pipeline — extract, classify, deduplicate, conflict-check, stage."""
    user_uid = session.created_by_uid
    granularity = session.granularity or "standard"

    # Step 1: Extract facts
    _publish_progress(session_uid_str, "Extracting facts...", 10)
    if session.input_type == "text" and session.source_text:
        all_facts = _extract_facts_from_text(
            session.source_text, db, user_uid,
            session_uid_str, granularity,
        )
    else:
        all_facts = _extract_facts_from_document(
            session, db, user_uid,
            session_uid_str, granularity,
        )

    sentences = [f.get("sentence", "") for f in all_facts if f.get("sentence")]
    if not sentences:
        raise RuntimeError("No facts extracted from document")

    # Step 2: Classify into taxonomy
    _publish_progress(session_uid_str, "Classifying into taxonomy...", 80)
    constraint_uids = (
        [str(u) for u in session.constraint_node_uids]
        if session.constraint_node_uids
        else None
    )
    classified = _classify_sync(
        sentences, db, session.program_node_uid, user_uid, constraint_uids
    )

    # Step 3: Deduplicate (Jaccard > 0.85)
    _publish_progress(session_uid_str, "Checking for duplicates and conflicts...", 90)
    existing_facts = _get_existing_facts(db, session.program_node_uid)
    existing_for_dedup = [
        {"sentence": s, "fact_uid": str(uid)} for s, uid in existing_facts
    ]
    classified_for_dedup = [{"sentence": c["sentence"]} for c in classified]
    deduped = deduplicate(classified_for_dedup, existing_for_dedup)

    # Merge dedup results into classified
    staged_data: list[dict[str, Any]] = []
    for i, (cls_result, dedup_result) in enumerate(zip(classified, deduped)):
        fact_data: dict[str, Any] = {
            "sentence": cls_result["sentence"],
            "suggested_node_uid": cls_result.get("suggested_node_uid"),
            "node_confidence": cls_result.get("node_confidence"),
            "node_alternatives": cls_result.get("node_alternatives", []),
            "metadata_tags": all_facts[i].get("metadata_tags", []) if i < len(all_facts) else [],
            "source_chunk_index": i,
            "status": "pending",
        }

        if dedup_result.get("duplicate_of"):
            fact_data["status"] = "duplicate"
            fact_data["duplicate_of_uid"] = dedup_result["duplicate_of"]
            fact_data["similarity_score"] = dedup_result.get("similarity")
        elif not cls_result.get("suggested_node_uid"):
            fact_data["status"] = "orphaned"

        staged_data.append(fact_data)

    # Step 4: Store in Postgres
    count = stage_facts_postgres(db, session.session_uid, staged_data)
    db.flush()

    # Step 5: Conflict detection on non-duplicate, non-orphaned facts
    pending_facts = db.execute(
        select(FcImportStagedFact).where(
            FcImportStagedFact.session_uid == session.session_uid,
            FcImportStagedFact.status == "pending",
        )
    ).scalars().all()

    if pending_facts and existing_facts:
        detections = _detect_conflicts_sync(
            list(pending_facts),
            existing_facts,
            user_uid,
        )
        for det in detections:
            for sf in pending_facts:
                if sf.staged_fact_uid == det["staged_fact_uid"]:
                    if det.get("type") == "duplicate":
                        sf.status = "duplicate"
                        sf.duplicate_of_uid = det["version_uid"]
                        sf.similarity_score = 0.0  # AI-detected, not Jaccard
                    else:
                        sf.status = "conflict"
                        sf.conflict_with_uid = det["version_uid"]
                    sf.conflict_reason = det.get("reason", "")
                    break

    _publish_progress(session_uid_str, "Checking for duplicates and conflicts...", 98)

    # Also write S3 backup
    try:
        s3_key = stage_facts_s3(session.session_uid, [{"sentence": s} for s in sentences])
        session.staged_facts_s3 = s3_key
    except Exception:
        log.warning("s3_backup_failed", session_uid=session_uid_str)

    session.status = "staged"
    _publish_progress(session_uid_str, "Ready for review", 100)
    log.info("import_analysis_complete", session_uid=session_uid_str, fact_count=count)


@celery_app.task(name="import_pipeline.rerun_analysis")  # type: ignore[misc]
def rerun_analysis(session_uid_str: str) -> None:
    """Re-run classification + conflict detection on existing staged facts."""
    with Session(_sync_engine) as db:
        session = db.get(FcImportSession, session_uid_str)
        if not session:
            return

        session.status = "analyzing"
        db.commit()

        try:
            _run_reanalysis(db, session, session_uid_str)
        except Exception as e:
            log.error("import_reanalysis_failed", session_uid=session_uid_str, error=str(e))
            session.status = "failed"
            session.error_message = str(e)
            _publish_progress(session_uid_str, f"Failed: {e}", -1)

        db.commit()


def _run_reanalysis(db: Session, session: FcImportSession, session_uid_str: str) -> None:
    """Re-classify and re-check conflicts without re-extracting."""
    user_uid = session.created_by_uid

    # Load existing staged facts
    staged = db.execute(
        select(FcImportStagedFact).where(
            FcImportStagedFact.session_uid == session.session_uid,
        ).order_by(FcImportStagedFact.source_chunk_index)
    ).scalars().all()

    if not staged:
        raise RuntimeError("No staged facts to re-analyze")

    sentences = [sf.display_sentence for sf in staged]

    # Re-classify
    _publish_progress(session_uid_str, "Classifying into taxonomy...", 30)
    constraint_uids = (
        [str(u) for u in session.constraint_node_uids]
        if session.constraint_node_uids
        else None
    )
    classified = _classify_sync(
        sentences, db, session.program_node_uid, user_uid, constraint_uids
    )

    # Update staged facts with new classification
    for sf, cls in zip(staged, classified):
        sf.suggested_node_uid = (
            UUID(cls["suggested_node_uid"]) if cls.get("suggested_node_uid") else None
        )
        sf.node_confidence = cls.get("node_confidence")
        sf.node_alternatives = cls.get("node_alternatives", [])
        if not sf.suggested_node_uid and sf.status not in ("duplicate",):
            sf.status = "orphaned"
        elif sf.status == "orphaned" and sf.suggested_node_uid:
            sf.status = "pending"

    # Re-check duplicates + conflicts
    _publish_progress(session_uid_str, "Checking for duplicates and conflicts...", 70)
    existing_facts = _get_existing_facts(db, session.program_node_uid)

    pending_facts = [sf for sf in staged if sf.status == "pending"]
    if pending_facts and existing_facts:
        detections = _detect_conflicts_sync(pending_facts, existing_facts, user_uid)
        for det in detections:
            for sf in pending_facts:
                if sf.staged_fact_uid == det["staged_fact_uid"]:
                    if det.get("type") == "duplicate":
                        sf.status = "duplicate"
                        sf.duplicate_of_uid = det["version_uid"]
                    else:
                        sf.status = "conflict"
                        sf.conflict_with_uid = det["version_uid"]
                    sf.conflict_reason = det.get("reason", "")
                    break

    session.status = "staged"
    _publish_progress(session_uid_str, "Ready for review", 100)
