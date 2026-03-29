"""Rate limit check (Redis-backed INCR + EXPIRE)."""

from artiFACT.kernel.auth.session import get_redis
from artiFACT.kernel.exceptions import RateLimited

DEFAULT_LIMITS: dict[str, int] = {
    "login": 10,
    "api_read": 200,
    "api_write": 50,
}

WINDOW_SECONDS = 3600


async def check_rate(identifier: str, action: str) -> None:
    """Increment rate counter and raise 429 if threshold exceeded."""
    r = await get_redis()
    key = f"rate:{action}:{identifier}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, WINDOW_SECONDS)
    limit = DEFAULT_LIMITS.get(action, 100)
    if count > limit:
        raise RateLimited(f"Rate limit exceeded for {action}")
