"""Core business logic for fact CRUD operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.events import publish
from artiFACT.kernel.exceptions import Conflict, Forbidden, NotFound
from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcUser
from artiFACT.kernel.permissions.resolver import can
from artiFACT.modules.facts.validators import (
    validate_duplicate,
    validate_effective_date,
    validate_sentence,
)
from artiFACT.modules.facts.versioning import create_version


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def create_fact(
    db: AsyncSession,
    node_uid: UUID,
    sentence: str,
    actor: FcUser,
    *,
    metadata_tags: list | None = None,
    source_reference: dict | None = None,
    effective_date: str | None = None,
    classification: str = "UNCLASSIFIED",
) -> tuple[FcFact, FcFactVersion]:
    """Create a new fact with its initial version."""
    if not await can(actor, "contribute", node_uid, db):
        raise Forbidden("Cannot create facts in this node", code="FORBIDDEN")

    node = await db.get(FcNode, node_uid)
    if not node:
        raise NotFound("Node not found", code="NODE_NOT_FOUND")

    validate_sentence(sentence)
    validate_effective_date(effective_date)
    await validate_duplicate(db, sentence, node_uid)

    fact = FcFact(
        node_uid=node_uid,
        created_by_uid=actor.user_uid,
    )
    db.add(fact)
    await db.flush()

    version = await create_version(
        db,
        fact,
        sentence,
        actor,
        metadata_tags=metadata_tags,
        source_reference=source_reference,
        effective_date=effective_date,
        classification=classification,
    )
    await db.flush()

    await publish(
        "fact.created",
        {
            "fact_uid": str(fact.fact_uid),
            "version_uid": str(version.version_uid),
            "node_uid": str(node_uid),
            "actor_uid": str(actor.user_uid),
            "state": version.state,
            "sentence": sentence,
        },
    )

    return fact, version


async def edit_fact(
    db: AsyncSession,
    fact_uid: UUID,
    sentence: str,
    actor: FcUser,
    *,
    metadata_tags: list | None = None,
    source_reference: dict | None = None,
    effective_date: str | None = None,
    classification: str = "UNCLASSIFIED",
    change_summary: str | None = None,
) -> tuple[FcFact, FcFactVersion]:
    """Edit a fact by creating a new version that supersedes the current one."""
    fact = await db.get(FcFact, fact_uid)
    if not fact:
        raise NotFound("Fact not found", code="FACT_NOT_FOUND")
    if fact.is_retired:
        raise Conflict("Cannot edit a retired fact", code="FACT_RETIRED")

    if not await can(actor, "contribute", fact.node_uid, db):
        raise Forbidden("Cannot edit facts in this node", code="FORBIDDEN")

    validate_sentence(sentence)
    validate_effective_date(effective_date)

    version = await create_version(
        db,
        fact,
        sentence,
        actor,
        metadata_tags=metadata_tags,
        source_reference=source_reference,
        effective_date=effective_date,
        classification=classification,
        change_summary=change_summary,
    )
    await db.flush()

    await publish(
        "fact.edited",
        {
            "fact_uid": str(fact.fact_uid),
            "version_uid": str(version.version_uid),
            "node_uid": str(fact.node_uid),
            "actor_uid": str(actor.user_uid),
            "state": version.state,
            "sentence": sentence,
        },
    )

    return fact, version


async def retire_fact(db: AsyncSession, fact_uid: UUID, actor: FcUser) -> FcFact:
    """Retire a fact (soft delete)."""
    fact = await db.get(FcFact, fact_uid)
    if not fact:
        raise NotFound("Fact not found", code="FACT_NOT_FOUND")
    if fact.is_retired:
        raise Conflict("Fact is already retired", code="ALREADY_RETIRED")

    if not await can(actor, "approve", fact.node_uid, db):
        raise Forbidden("Cannot retire facts in this node", code="FORBIDDEN")

    fact.is_retired = True
    fact.retired_at = _utcnow()
    fact.retired_by_uid = actor.user_uid

    await publish(
        "fact.retired",
        {
            "fact_uid": str(fact.fact_uid),
            "node_uid": str(fact.node_uid),
            "actor_uid": str(actor.user_uid),
        },
    )

    return fact


async def unretire_fact(db: AsyncSession, fact_uid: UUID, actor: FcUser) -> FcFact:
    """Unretire a previously retired fact."""
    fact = await db.get(FcFact, fact_uid)
    if not fact:
        raise NotFound("Fact not found", code="FACT_NOT_FOUND")
    if not fact.is_retired:
        raise Conflict("Fact is not retired", code="NOT_RETIRED")

    if not await can(actor, "approve", fact.node_uid, db):
        raise Forbidden("Cannot unretire facts in this node", code="FORBIDDEN")

    fact.is_retired = False
    fact.retired_at = None
    fact.retired_by_uid = None

    await publish(
        "fact.unretired",
        {
            "fact_uid": str(fact.fact_uid),
            "node_uid": str(fact.node_uid),
            "actor_uid": str(actor.user_uid),
        },
    )

    return fact


async def get_fact_versions(db: AsyncSession, fact_uid: UUID) -> list[FcFactVersion]:
    """Return all versions for a fact, newest first."""
    fact = await db.get(FcFact, fact_uid)
    if not fact:
        raise NotFound("Fact not found", code="FACT_NOT_FOUND")

    stmt = (
        select(FcFactVersion)
        .where(FcFactVersion.fact_uid == fact_uid)
        .order_by(FcFactVersion.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_facts_by_node(
    db: AsyncSession,
    node_uid: UUID,
    *,
    include_retired: bool = False,
) -> list[FcFact]:
    """Return facts for a node."""
    stmt = select(FcFact).where(FcFact.node_uid == node_uid)
    if not include_retired:
        stmt = stmt.where(FcFact.is_retired.is_(False))
    stmt = stmt.order_by(FcFact.created_at.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())
