"""Stage extracted facts — primary storage in PostgreSQL, optional S3 backup."""

import json
from typing import Any, cast
from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from artiFACT.kernel.models import FcImportStagedFact
from artiFACT.kernel.s3 import download_json, upload_json

log = structlog.get_logger()


def stage_facts_s3(session_uid: UUID, facts: list[dict[str, Any]]) -> str:
    """Write staged facts JSON to S3 and return the S3 key (backup)."""
    staged_key = f"imports/{session_uid}/staged.json"
    staged = [
        {
            "index": i,
            "sentence": f.get("sentence", ""),
            "metadata_tags": f.get("metadata_tags", []),
            "source_reference": f.get("source_reference"),
            "duplicate_of": f.get("duplicate_of"),
            "similarity": f.get("similarity"),
            "accepted": True,
        }
        for i, f in enumerate(facts)
    ]
    upload_json(staged_key, json.dumps(staged))
    return staged_key


def stage_facts_postgres(
    db: Session,
    session_uid: UUID,
    classified_facts: list[dict[str, Any]],
) -> int:
    """Insert classified facts into fc_import_staged_fact (sync, for Celery)."""
    count = 0
    for i, fact in enumerate(classified_facts):
        staged = FcImportStagedFact(
            session_uid=session_uid,
            display_sentence=fact.get("sentence", ""),
            suggested_node_uid=_parse_uid(fact.get("suggested_node_uid")),
            node_confidence=fact.get("node_confidence"),
            node_alternatives=fact.get("node_alternatives", []),
            status=fact.get("status", "pending"),
            duplicate_of_uid=_parse_uid(fact.get("duplicate_of_uid")),
            similarity_score=fact.get("similarity_score"),
            conflict_with_uid=_parse_uid(fact.get("conflict_with_uid")),
            conflict_reason=fact.get("conflict_reason"),
            source_chunk_index=fact.get("source_chunk_index", i),
            metadata_tags=fact.get("metadata_tags", []),
        )
        db.add(staged)
        count += 1
    return count


async def stage_facts_postgres_async(
    db: AsyncSession,
    session_uid: UUID,
    classified_facts: list[dict[str, Any]],
) -> int:
    """Insert classified facts into fc_import_staged_fact (async)."""
    count = 0
    for i, fact in enumerate(classified_facts):
        staged = FcImportStagedFact(
            session_uid=session_uid,
            display_sentence=fact.get("sentence", ""),
            suggested_node_uid=_parse_uid(fact.get("suggested_node_uid")),
            node_confidence=fact.get("node_confidence"),
            node_alternatives=fact.get("node_alternatives", []),
            status=fact.get("status", "pending"),
            duplicate_of_uid=_parse_uid(fact.get("duplicate_of_uid")),
            similarity_score=fact.get("similarity_score"),
            conflict_with_uid=_parse_uid(fact.get("conflict_with_uid")),
            conflict_reason=fact.get("conflict_reason"),
            source_chunk_index=fact.get("source_chunk_index", i),
            metadata_tags=fact.get("metadata_tags", []),
        )
        db.add(staged)
        count += 1
    return count


async def delete_staged_facts(db: AsyncSession, session_uid: UUID) -> int:
    """Delete all staged facts for a session. Returns count deleted."""
    result = await db.execute(
        delete(FcImportStagedFact).where(FcImportStagedFact.session_uid == session_uid)
    )
    return result.rowcount  # type: ignore[return-value]


async def load_staged_facts_postgres(
    db: AsyncSession, session_uid: UUID
) -> list[FcImportStagedFact]:
    """Load staged facts from Postgres."""
    result = await db.execute(
        select(FcImportStagedFact)
        .where(FcImportStagedFact.session_uid == session_uid)
        .order_by(FcImportStagedFact.source_chunk_index)
    )
    return list(result.scalars().all())


# Keep legacy S3 functions for backward compat with existing proposer
def stage_facts(session_uid: UUID, facts: list[dict[str, Any]]) -> str:
    """Legacy S3-based staging (kept for backward compat)."""
    return stage_facts_s3(session_uid, facts)


def load_staged_facts(s3_key: str) -> list[dict[str, Any]]:
    """Load staged facts from S3 (legacy)."""
    return cast(list[dict[str, Any]], json.loads(download_json(s3_key)))


def _parse_uid(value: Any) -> UUID | None:
    """Parse a UUID from string or return None."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, AttributeError):
        return None
