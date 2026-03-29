"""Read active grants for a user (cached per-request)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcNodePermission


async def get_active_grants(
    db: AsyncSession, user_uid: uuid.UUID
) -> list[FcNodePermission]:
    """Load all active (non-revoked) grants for a user."""
    result = await db.execute(
        select(FcNodePermission).where(
            FcNodePermission.user_uid == user_uid,
            FcNodePermission.revoked_at.is_(None),
        )
    )
    return list(result.scalars().all())
