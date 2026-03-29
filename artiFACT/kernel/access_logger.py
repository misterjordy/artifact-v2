"""ZT Pillar 5 — Data access logging for insider-threat-relevant actions."""

import uuid

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcEventLog

logger = structlog.get_logger()


async def log_data_access(
    db: AsyncSession,
    user_uid: uuid.UUID,
    action: str,
    detail: dict[str, Any],
) -> None:
    """Log data-exfiltration-relevant access events. Non-blocking best-effort.

    Called from: export/factsheet, ai/chat, sync/changes, sync/full.
    NOT called from: page views, search, tree browse (noise).
    """
    event = FcEventLog(
        entity_type="access",
        entity_uid=user_uid,
        event_type=f"access.{action}",
        payload=detail,
        actor_uid=user_uid,
    )
    db.add(event)
    await db.flush()
    logger.info("data_access_logged", action=action, user_uid=str(user_uid))
