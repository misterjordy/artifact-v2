"""Revise language: reject original + create revised version + publish (atomic)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.events import publish
from artiFACT.kernel.exceptions import Conflict, Forbidden, NotFound
from artiFACT.kernel.models import FcFact, FcFactVersion, FcUser
from artiFACT.modules.facts.state_machine import transition
from artiFACT.modules.queue.scope_resolver import get_approvable_nodes


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def revise_and_publish(
    db: AsyncSession,
    version_uid: uuid.UUID,
    revised_sentence: str,
    actor: FcUser,
    *,
    note: str | None = None,
) -> FcFactVersion:
    """Reject original version + create revised version + publish — all in one transaction."""
    version = await db.get(FcFactVersion, version_uid)
    if not version:
        raise NotFound("Version not found")
    if version.state != "proposed":
        raise Conflict("Not a pending proposal")

    fact = await db.get(FcFact, version.fact_uid)
    if not fact:
        raise NotFound("Fact not found")

    approvable = await get_approvable_nodes(db, actor)
    if fact.node_uid not in approvable:
        raise Forbidden("This fact is outside your approval scope")

    async with db.begin_nested():
        await transition(version, "rejected", actor)

        revised = FcFactVersion(
            fact_uid=fact.fact_uid,
            display_sentence=revised_sentence,
            metadata_tags=version.metadata_tags or [],
            source_reference=version.source_reference,
            effective_date=version.effective_date,
            classification=version.classification,
            change_summary=f"Revised by approver: {note}" if note else "Revised by approver",
            supersedes_version_uid=version.version_uid,
            created_by_uid=actor.user_uid,
            state="published",
            published_at=_utcnow(),
        )
        db.add(revised)
        await db.flush()

        fact.current_published_version_uid = revised.version_uid

    await publish(
        "version.rejected",
        {
            "version_uid": str(version.version_uid),
            "fact_uid": str(version.fact_uid),
            "actor_uid": str(actor.user_uid),
            "note": note or "Revised",
        },
    )
    await publish(
        "version.published",
        {
            "version_uid": str(revised.version_uid),
            "fact_uid": str(fact.fact_uid),
            "actor_uid": str(actor.user_uid),
            "old_state": "proposed",
            "new_state": "published",
        },
    )

    return revised
