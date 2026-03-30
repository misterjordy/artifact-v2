"""Version creation logic."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcFact, FcFactVersion, FcUser
from artiFACT.kernel.permissions.resolver import can


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def create_version(
    db: AsyncSession,
    fact: FcFact,
    sentence: str,
    actor: FcUser,
    *,
    metadata_tags: list[str] | None = None,
    source_reference: dict[str, Any] | None = None,
    effective_date: str | None = None,
    classification: str = "UNCLASSIFIED",
    change_summary: str | None = None,
    auto_approve: bool = False,
) -> FcFactVersion:
    """Create a new fact version.

    Auto-publishes only when auto_approve=True AND actor has approve
    permission. Default is proposed for all users.
    """
    version = FcFactVersion(
        fact_uid=fact.fact_uid,
        display_sentence=sentence,
        metadata_tags=metadata_tags or [],
        source_reference=source_reference,
        effective_date=effective_date,
        classification=classification,
        change_summary=change_summary,
        supersedes_version_uid=fact.current_published_version_uid,
        created_by_uid=actor.user_uid,
    )

    if auto_approve and await can(actor, "approve", fact.node_uid, db):
        version.state = "published"
        version.published_at = _utcnow()
    else:
        version.state = "proposed"

    db.add(version)
    await db.flush()

    if version.state == "published":
        fact.current_published_version_uid = version.version_uid

    return version
