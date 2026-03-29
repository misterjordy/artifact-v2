"""Search-specific test fixtures."""

import pytest_asyncio

from artiFACT.kernel.auth.session import get_redis
from artiFACT.modules.search.acronym_miner import ACRONYM_CACHE_KEY


@pytest_asyncio.fixture(autouse=True)
async def _clear_acronym_cache():
    """Clear the Redis acronym cache before and after each test."""
    r = await get_redis()
    await r.delete(ACRONYM_CACHE_KEY)
    yield
    await r.delete(ACRONYM_CACHE_KEY)
