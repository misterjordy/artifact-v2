"""Staged facts to real facts — all-or-nothing transaction (regression: v1 I-MAINT-02)."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.events import publish
from artiFACT.kernel.exceptions import Conflict, Forbidden, NotFound
from artiFACT.kernel.models import FcFact, FcFactVersion, FcImportSession, FcUser
from artiFACT.kernel.permissions.resolver import can
from artiFACT.modules.import_pipeline.stager import load_staged_facts


async def propose_facts(
    db: AsyncSession,
    session_uid: UUID,
    accepted_indices: list[int],
    actor: FcUser,
) -> int:
    """Create real facts from accepted staged facts in a single transaction."""
    session = await db.get(FcImportSession, session_uid)
    if not session:
        raise NotFound("Import session not found", code="SESSION_NOT_FOUND")

    if session.status != "staged":
        raise Conflict(
            f"Session is not staged (current: {session.status})",
            code="INVALID_STATUS",
        )

    if not await can(actor, "contribute", session.program_node_uid, db):
        raise Forbidden("Cannot create facts in this node", code="FORBIDDEN")

    if not session.staged_facts_s3:
        raise NotFound("No staged facts found", code="NO_STAGED_FACTS")

    staged = load_staged_facts(session.staged_facts_s3)

    to_create = [f for f in staged if f["index"] in accepted_indices]
    if not to_create:
        raise Conflict("No facts selected for import", code="NO_FACTS_SELECTED")

    created_count = 0
    async with db.begin_nested():
        for staged_fact in to_create:
            fact = FcFact(
                node_uid=session.program_node_uid,
                created_by_uid=actor.user_uid,
            )
            db.add(fact)
            await db.flush()

            version = FcFactVersion(
                fact_uid=fact.fact_uid,
                state="proposed",
                display_sentence=staged_fact["sentence"],
                metadata_tags=staged_fact.get("metadata_tags", []),
                source_reference=staged_fact.get("source_reference"),
                effective_date=str(session.effective_date),
                created_by_uid=actor.user_uid,
            )
            db.add(version)
            created_count += 1

        session.status = "proposed"

    await db.flush()

    await publish(
        "import.proposed",
        {
            "session_uid": str(session_uid),
            "created_count": created_count,
            "actor_uid": str(actor.user_uid),
            "node_uid": str(session.program_node_uid),
        },
    )

    return created_count
