"""AI-powered fact extraction (Celery task)."""

import json
import os
from typing import Any

import httpx
import redis as sync_redis
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from artiFACT.kernel.background import app as celery_app
from artiFACT.kernel.crypto import decrypt
from artiFACT.kernel.models import FcFactVersion, FcImportSession, FcUser, FcUserAiKey
from artiFACT.kernel.s3 import download_bytes
from artiFACT.modules.import_pipeline.deduplicator import deduplicate
from artiFACT.modules.import_pipeline.extractors import get_extractor
from artiFACT.modules.import_pipeline.stager import stage_facts

EXTRACTION_PROMPT = """You are a fact extraction engine. Given a document chunk, extract discrete factual statements.

Return a JSON object with a "facts" array. Each fact has:
- "sentence": a single factual statement (10-2000 chars)
- "metadata_tags": array of relevant tags
- "source_reference": {"section": "...", "page": "..."} if identifiable

Extract ONLY factual statements. Do not include opinions, instructions, or metadata.
Be precise and preserve technical details."""

_SYNC_DB_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://artifact:artifact_dev@postgres:5432/artifact_db"
).replace("+asyncpg", "")
_sync_engine = create_engine(_SYNC_DB_URL, pool_pre_ping=True)

_redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
_redis_client = sync_redis.from_url(_redis_url, decode_responses=True)  # type: ignore[no-untyped-call]  # redis stub gap


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


def _call_ai(api_key: str, provider: str, model: str, messages: list[dict[str, Any]]) -> str:
    """Synchronous AI provider call."""
    if provider in ("openai", "azure_openai"):
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": messages,
                "max_tokens": 4096,
                "response_format": {"type": "json_object"},
            },
            timeout=120,
        )
        resp.raise_for_status()
        return str(resp.json()["choices"][0]["message"]["content"])
    elif provider == "anthropic":
        system_content = ""
        api_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                api_messages.append(msg)
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 4096,
                "system": system_content,
                "messages": api_messages,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return str(resp.json()["content"][0]["text"])
    else:
        raise ValueError(f"Unsupported provider: {provider}")


DEFAULT_MODELS = {"openai": "gpt-4o", "anthropic": "claude-sonnet-4-20250514"}


def _parse_extracted_facts(response_text: str) -> list[dict[str, Any]]:
    """Parse AI response into list of fact dicts."""
    try:
        data = json.loads(response_text)
        return data.get("facts", [])  # type: ignore[no-any-return]  # JSON parsed data
    except json.JSONDecodeError:
        return []


@celery_app.task(name="import_pipeline.analyze_document")  # type: ignore[misc]  # Celery task decorator is untyped
def analyze_document(session_uid_str: str) -> None:
    """Celery task: extract text, call AI, deduplicate, stage."""
    with Session(_sync_engine) as db:
        session = db.get(FcImportSession, session_uid_str)
        if not session:
            return

        session.status = "analyzing"
        db.commit()

        try:
            if not session.source_s3_key:
                raise RuntimeError("No source S3 key")
            content = download_bytes(session.source_s3_key)

            extractor = get_extractor(session.source_filename)
            text = extractor.extract(content)
            _publish_progress(session_uid_str, "Extracted text", 10)

            chunks = _chunk_text(text)
            _publish_progress(session_uid_str, f"Split into {len(chunks)} chunks", 20)

            db.get(FcUser, session.created_by_uid)
            ai_key = db.execute(
                select(FcUserAiKey).where(FcUserAiKey.user_uid == session.created_by_uid)
            ).scalar_one_or_none()

            if not ai_key:
                raise RuntimeError("No AI key configured for user")

            plaintext_key = decrypt(ai_key.encrypted_key)
            model = ai_key.model_override or DEFAULT_MODELS.get(ai_key.provider, "gpt-4o")

            all_facts: list[dict[str, Any]] = []
            for i, chunk in enumerate(chunks):
                response = _call_ai(
                    plaintext_key,
                    ai_key.provider,
                    model,
                    [
                        {"role": "system", "content": EXTRACTION_PROMPT},
                        {"role": "user", "content": chunk},
                    ],
                )
                facts = _parse_extracted_facts(response)
                all_facts.extend(facts)
                pct = 20 + (60 * (i + 1) / len(chunks))
                _publish_progress(
                    session_uid_str, f"Extracted from chunk {i + 1}/{len(chunks)}", pct
                )

            db.execute(
                select(FcFactVersion)
                .join(
                    FcImportSession,
                    FcFactVersion.fact_uid == FcImportSession.program_node_uid,
                )
                .where(False)  # type: ignore[arg-type]
            ).scalars().all()

            from sqlalchemy import text as sa_text

            existing_rows = db.execute(
                sa_text(
                    "SELECT fv.display_sentence, f.fact_uid "
                    "FROM fc_fact_version fv "
                    "JOIN fc_fact f ON fv.fact_uid = f.fact_uid "
                    "WHERE f.node_uid = :node_uid AND f.is_retired = false"
                ),
                {"node_uid": str(session.program_node_uid)},
            ).fetchall()

            existing_facts = [
                {"sentence": row[0], "fact_uid": str(row[1])} for row in existing_rows
            ]

            deduped = deduplicate(all_facts, existing_facts)
            _publish_progress(session_uid_str, f"{len(deduped)} unique facts found", 90)

            staged_key = stage_facts(session.session_uid, deduped)
            session.staged_facts_s3 = staged_key
            session.status = "staged"
            _publish_progress(session_uid_str, "Ready for review", 100)

        except Exception as e:
            session.status = "failed"
            session.error_message = str(e)
            _publish_progress(session_uid_str, f"Failed: {e}", -1)

        db.commit()
