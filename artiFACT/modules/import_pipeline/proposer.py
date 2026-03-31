"""Propose staged facts into the real corpus — all-or-nothing transaction."""

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.events import publish
from artiFACT.kernel.exceptions import Conflict, Forbidden, NotFound
from artiFACT.kernel.models import (
    FcFact,
    FcFactComment,
    FcFactVersion,
    FcImportSession,
    FcImportStagedFact,
    FcUser,
)
from artiFACT.modules.facts.service import create_fact, edit_fact

log = structlog.get_logger()


def make_import_tag() -> str:
    """Generate import tag: #importYYYYMMDDHHMMSS."""
    now = datetime.now(timezone.utc)
    return f"#import{now.strftime('%Y%m%d%H%M%S')}"


def _effective_date_str(session: FcImportSession) -> str:
    """Format effective_date as YYYY-MM-DD string regardless of column type."""
    d = session.effective_date
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    return str(d)[:10]


def _source_name(session: FcImportSession) -> str:
    """Human-readable source name for import comments."""
    if session.input_type == "text":
        return "pasted text"
    return session.source_filename


async def count_ready_facts(db: AsyncSession, session_uid: UUID) -> int:
    """Count staged facts ready for proposal (accepted or pending with a node)."""
    result = await db.execute(
        select(func.count())
        .select_from(FcImportStagedFact)
        .where(
            FcImportStagedFact.session_uid == session_uid,
            FcImportStagedFact.status.in_(["accepted", "pending"]),
            FcImportStagedFact.suggested_node_uid.isnot(None),
        )
    )
    return result.scalar_one()


async def count_unassigned_facts(db: AsyncSession, session_uid: UUID) -> int:
    """Count non-skippable facts that have no target node."""
    result = await db.execute(
        select(func.count())
        .select_from(FcImportStagedFact)
        .where(
            FcImportStagedFact.session_uid == session_uid,
            FcImportStagedFact.status.in_(["accepted", "pending"]),
            FcImportStagedFact.suggested_node_uid.is_(None),
        )
    )
    return result.scalar_one()


async def propose_import(
    db: AsyncSession,
    session_uid: UUID,
    actor: FcUser,
) -> dict[str, int]:
    """Propose all staged facts into the corpus. All-or-nothing transaction."""
    session = await db.get(FcImportSession, session_uid)
    if not session:
        raise NotFound("Import session not found", code="SESSION_NOT_FOUND")

    tag = make_import_tag()
    source = _source_name(session)
    created = 0
    edited = 0
    skipped = 0

    staged_result = await db.execute(
        select(FcImportStagedFact)
        .where(FcImportStagedFact.session_uid == session_uid)
        .order_by(FcImportStagedFact.source_chunk_index)
    )
    staged_facts = staged_result.scalars().all()

    async with db.begin_nested():
        for sf in staged_facts:
            if _should_skip(sf):
                skipped += 1
                continue

            if sf.resolution == "keep_new":
                await _propose_keep_new(db, sf, actor, session, tag, source)
                edited += 1
            else:
                await _propose_new_fact(db, sf, actor, session, tag, source)
                created += 1

        session.status = "proposed"
        session.completed_at = datetime.now(timezone.utc)

    await db.flush()

    await publish(
        "import.proposed",
        {
            "session_uid": str(session_uid),
            "created_count": created,
            "edited_count": edited,
            "skipped_count": skipped,
            "actor_uid": str(actor.user_uid),
            "node_uid": str(session.program_node_uid),
            "import_tag": tag,
        },
    )

    log.info(
        "import_proposed",
        session_uid=str(session_uid),
        created=created,
        edited=edited,
        skipped=skipped,
    )

    return {"created": created, "edited": edited, "skipped": skipped}


def _should_skip(sf: FcImportStagedFact) -> bool:
    """Determine if a staged fact should be skipped during propose."""
    if sf.status in ("rejected", "deleted", "orphaned"):
        return True
    if sf.resolution == "keep_existing":
        return True
    if sf.suggested_node_uid is None and sf.resolution != "keep_new":
        return True
    return False


async def _propose_new_fact(
    db: AsyncSession,
    sf: FcImportStagedFact,
    actor: FcUser,
    session: FcImportSession,
    tag: str,
    source: str,
) -> None:
    """Case 1: Create a new fact for accepted/pending staged facts."""
    _fact, version = await create_fact(
        db=db,
        node_uid=sf.suggested_node_uid,
        sentence=sf.display_sentence,
        actor=actor,
        metadata_tags=sf.metadata_tags or [],
        effective_date=_effective_date_str(session),
        classification="UNCLASSIFIED",
        auto_approve=False,
    )

    comment = FcFactComment(
        version_uid=version.version_uid,
        comment_type="comment",
        body=f"{tag} — imported from {source}",
        created_by_uid=actor.user_uid,
    )
    db.add(comment)


async def _propose_keep_new(
    db: AsyncSession,
    sf: FcImportStagedFact,
    actor: FcUser,
    session: FcImportSession,
    tag: str,
    source: str,
) -> None:
    """Case 2: KEEP NEW — create proposed edit on existing fact."""
    existing_version_uid = sf.duplicate_of_uid or sf.conflict_with_uid
    if not existing_version_uid:
        raise Conflict("keep_new fact has no existing version reference", code="MISSING_REF")

    existing_version = await db.get(FcFactVersion, existing_version_uid)
    if not existing_version:
        raise NotFound("Referenced existing version not found", code="VERSION_NOT_FOUND")

    reason = sf.conflict_reason or "duplicate resolution"
    change_summary = f"Import correction: {reason}"

    _fact, new_version = await edit_fact(
        db=db,
        fact_uid=existing_version.fact_uid,
        sentence=sf.display_sentence,
        actor=actor,
        metadata_tags=sf.metadata_tags or [],
        effective_date=_effective_date_str(session),
        classification="UNCLASSIFIED",
        change_summary=change_summary,
        auto_approve=False,
    )

    comment = FcFactComment(
        version_uid=new_version.version_uid,
        comment_type="comment",
        body=f"{tag} — correction from {source}",
        created_by_uid=actor.user_uid,
    )
    db.add(comment)


# Legacy function kept for backward compatibility with old tests
async def propose_facts(
    db: AsyncSession,
    session_uid: UUID,
    accepted_indices: list[int],
    actor: FcUser,
) -> int:
    """Legacy propose — delegates to new propose_import."""
    result = await propose_import(db, session_uid, actor)
    return result["created"] + result["edited"]
