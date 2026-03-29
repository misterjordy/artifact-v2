"""Feature flag CRUD from fc_system_config."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.events import publish
from artiFACT.kernel.models import FcSystemConfig


async def list_config(db: AsyncSession) -> list[FcSystemConfig]:
    """Return all config entries."""
    result = await db.execute(select(FcSystemConfig).order_by(FcSystemConfig.key))
    return list(result.scalars().all())


async def get_config(db: AsyncSession, key: str) -> FcSystemConfig | None:
    """Return a single config entry by key."""
    return await db.get(FcSystemConfig, key)


async def upsert_config(
    db: AsyncSession, key: str, value: dict, actor_uid: uuid.UUID
) -> FcSystemConfig:
    """Create or update a config entry and publish audit event."""
    existing = await db.get(FcSystemConfig, key)
    old_value = existing.value if existing else None

    if existing:
        existing.value = value
        existing.updated_at = datetime.now(timezone.utc)
        existing.updated_by_uid = actor_uid
        await db.flush()
        row = existing
    else:
        row = FcSystemConfig(
            key=key,
            value=value,
            updated_by_uid=actor_uid,
        )
        db.add(row)
        await db.flush()

    await publish("admin.config_changed", {
        "key": key,
        "old_value": old_value,
        "new_value": value,
        "actor_uid": str(actor_uid),
    })

    return row
