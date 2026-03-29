"""Document generation orchestrator — Celery task with SSE progress."""

import json
import uuid

import redis

from artiFACT.kernel.background import app as celery_app
from artiFACT.kernel.config import settings
from artiFACT.kernel.s3 import get_s3_client, upload_bytes
from artiFACT.modules.export.docgen.docx_builder import build_docx
from artiFACT.modules.export.docgen.prefilter import (
    assign_facts_to_sections,
    score_facts_for_section,
)
from artiFACT.modules.export.docgen.synthesizer import synthesize_section


def _publish_progress(
    session_uid: str,
    stage: str,
    percent: float,
    download_url: str | None = None,
) -> None:
    """Publish progress to Redis for SSE consumption."""
    r = redis.from_url(settings.REDIS_URL)
    data = {
        "session_uid": session_uid,
        "stage": stage,
        "percent": percent,
        "download_url": download_url,
    }
    r.publish(f"docgen:{session_uid}", json.dumps(data))
    r.set(f"docgen:status:{session_uid}", json.dumps(data), ex=3600)


def _get_sync_engine():
    """Get synchronous DB engine for use in Celery tasks."""
    from sqlalchemy import create_engine

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
    return create_engine(sync_url)


@celery_app.task(name="export.generate_document")
def generate_document(
    session_uid: str,
    node_uids: list[str],
    template_uid: str,
    actor_uid: str,
    ai_provider_config: dict | None = None,
) -> dict:
    """Generate a DOCX document as a background Celery task.

    Steps:
    1. Load template sections
    2. Load all facts for the given nodes
    3. Two-pass prefilter: score all sections, then assign
    4. Synthesize text per section
    5. Build DOCX
    6. Upload to S3
    7. Publish completion with download URL
    """
    import asyncio

    engine = _get_sync_engine()

    with engine.connect() as conn:
        from sqlalchemy import text

        # Load template
        row = conn.execute(
            text(
                "SELECT name, abbreviation, sections FROM fc_document_template WHERE template_uid = :uid"
            ),
            {"uid": template_uid},
        ).fetchone()
        if not row:
            _publish_progress(session_uid, "Error: template not found", 0)
            return {"error": "Template not found"}

        template_name = row[0]
        _ = row[1]
        sections = row[2] if isinstance(row[2], list) else json.loads(row[2])

        # Load facts
        node_uid_list = [uuid.UUID(u) for u in node_uids]
        fact_rows = conn.execute(
            text("""
                SELECT fv.display_sentence, fv.classification, fv.metadata_tags,
                       fv.effective_date, fv.last_verified_date, fv.state,
                       n.title as node_title
                FROM fc_fact f
                JOIN fc_fact_version fv ON f.current_published_version_uid = fv.version_uid
                JOIN fc_node n ON f.node_uid = n.node_uid
                WHERE f.node_uid = ANY(:node_uids)
                  AND NOT f.is_retired
                  AND fv.state IN ('published', 'signed')
            """),
            {"node_uids": node_uid_list},
        ).fetchall()

        facts = []
        overall_classification = "UNCLASSIFIED"
        for r in fact_rows:
            facts.append(
                {
                    "sentence": r[0],
                    "classification": r[1] or "UNCLASSIFIED",
                    "tags": r[2] or [],
                    "effective_date": r[3],
                    "last_verified": r[4],
                    "state": r[5],
                    "node": r[6],
                }
            )
            if r[1] and "CUI" in (r[1] or "").upper():
                overall_classification = r[1]

    _publish_progress(session_uid, "Loaded facts", 10)

    # Prefilter (use mock AI for now — real AI integration uses provider)
    async def _mock_ai_call(prompt: str) -> str:
        """Default AI call that distributes facts evenly."""
        scores = {}
        for i in range(len(facts)):
            scores[str(i)] = 0.5
        return json.dumps({"scores": scores})

    ai_call = _mock_ai_call

    loop = asyncio.new_event_loop()

    affinity_scores = {}
    for i, section in enumerate(sections):
        pct = 10 + (i / len(sections)) * 30
        _publish_progress(session_uid, f"Scoring: {section['title']}", pct)
        scores = loop.run_until_complete(score_facts_for_section(ai_call, facts, section, sections))
        affinity_scores[section["key"]] = scores

    assignments = assign_facts_to_sections(affinity_scores, facts)

    _publish_progress(session_uid, "Synthesizing sections", 40)

    section_outputs = {}
    for i, section in enumerate(sections):
        pct = 40 + (i / len(sections)) * 40
        _publish_progress(session_uid, f"Writing: {section['title']}", pct)
        assigned = assignments.get(section["key"], [])
        text_out = loop.run_until_complete(
            synthesize_section(ai_call, assigned, section["prompt"], section["title"])
        )
        section_outputs[section["key"]] = text_out

    loop.close()

    _publish_progress(session_uid, "Building document", 85)
    docx_bytes = build_docx(section_outputs, sections, template_name, overall_classification)

    _publish_progress(session_uid, "Uploading to storage", 90)
    s3_key = f"exports/{actor_uid}/{session_uid}.docx"
    upload_bytes(
        s3_key,
        docx_bytes,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    # Generate presigned URL
    s3_client = get_s3_client()
    download_url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": s3_key},
        ExpiresIn=86400,
    )

    _publish_progress(session_uid, "Document ready", 100, download_url=download_url)

    # Store metadata for download_manager verification
    r = redis.from_url(settings.REDIS_URL)
    r.set(
        f"docgen:meta:{session_uid}",
        json.dumps({"actor_uid": actor_uid, "s3_key": s3_key}),
        ex=86400,
    )

    return {"session_uid": session_uid, "download_url": download_url, "s3_key": s3_key}
