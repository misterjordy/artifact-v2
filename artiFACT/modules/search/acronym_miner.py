"""Extract acronyms from the fact corpus, cache in Redis."""

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.session import get_redis
from artiFACT.kernel.events import subscribe
from artiFACT.kernel.models import FcFactVersion

ACRONYM_CACHE_KEY = "acronyms"
ACRONYM_TTL = 3600

_ACRONYM_RE = re.compile(r"\b([A-Z]{2,})\b")


async def mine_acronyms(db: AsyncSession) -> list[dict[str, str | int]]:
    """Extract unique acronyms from fc_fact_version.display_sentence, cached in Redis."""
    r = await get_redis()
    cached = await r.get(ACRONYM_CACHE_KEY)
    if cached:
        return json.loads(cached)  # type: ignore[no-any-return]  # cached JSON data

    stmt = select(FcFactVersion.display_sentence).where(
        FcFactVersion.state.in_(["published", "signed"])
    )
    result = await db.execute(stmt)
    sentences = result.scalars().all()

    counts: dict[str, int] = {}
    for sentence in sentences:
        for match in _ACRONYM_RE.findall(sentence):
            counts[match] = counts.get(match, 0) + 1

    entries = [{"acronym": k, "count": v} for k, v in sorted(counts.items())]
    await r.setex(ACRONYM_CACHE_KEY, ACRONYM_TTL, json.dumps(entries))
    return entries  # type: ignore[return-value]  # dict values are str | int at runtime


async def invalidate_acronym_cache(_payload: dict[str, Any]) -> None:
    """Event handler: clear acronym cache when a fact is published."""
    r = await get_redis()
    await r.delete(ACRONYM_CACHE_KEY)


def register_subscribers() -> None:
    """Wire up event bus subscriptions for acronym cache invalidation."""
    subscribe("fact.published", invalidate_acronym_cache)
