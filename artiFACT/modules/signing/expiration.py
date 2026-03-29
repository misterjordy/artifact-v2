"""Signature expiration logic (optional expires_at on signatures)."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcSignature


async def get_expired_signatures(db: AsyncSession) -> list[FcSignature]:
    """Return all signatures that have passed their expires_at."""
    now = datetime.now(timezone.utc)
    stmt = select(FcSignature).where(
        FcSignature.expires_at.isnot(None),
        FcSignature.expires_at < now,
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
