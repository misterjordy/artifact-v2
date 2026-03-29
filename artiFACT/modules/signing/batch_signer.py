"""Batch version state update — one UPDATE WHERE IN, one transaction."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcFact, FcFactVersion


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_published_versions(
    db: AsyncSession, node_uids: list[uuid.UUID]
) -> list[FcFactVersion]:
    """Collect all published versions under the given nodes (one query)."""
    stmt = (
        select(FcFactVersion)
        .join(FcFact, FcFactVersion.fact_uid == FcFact.fact_uid)
        .where(
            FcFact.node_uid.in_(node_uids),
            FcFact.is_retired.is_(False),
            FcFact.current_published_version_uid == FcFactVersion.version_uid,
            FcFactVersion.state == "published",
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def batch_sign_versions(
    db: AsyncSession, versions: list[FcFactVersion]
) -> None:
    """Batch UPDATE versions to 'signed' and update facts — one query each."""
    if not versions:
        return

    now = _utcnow()
    version_uids = [v.version_uid for v in versions]

    # One batch UPDATE for all versions
    await db.execute(
        update(FcFactVersion)
        .where(FcFactVersion.version_uid.in_(version_uids))
        .values(state="signed", signed_at=now)
    )

    # One batch UPDATE for facts: set current_signed_version_uid
    fact_to_version = {v.fact_uid: v.version_uid for v in versions}
    for fact_uid, ver_uid in fact_to_version.items():
        await db.execute(
            update(FcFact)
            .where(FcFact.fact_uid == fact_uid)
            .values(current_signed_version_uid=ver_uid)
        )

