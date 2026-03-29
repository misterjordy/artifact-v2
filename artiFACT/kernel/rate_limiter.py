"""Rate limit check (Redis-backed INCR + EXPIRE) — per-endpoint tuning."""

from artiFACT.kernel.auth.session import get_redis
from artiFACT.kernel.exceptions import RateLimited

# Per-endpoint rate limits: (max_requests, window_seconds)
RATE_LIMITS: dict[str, tuple[int, int]] = {
    "auth/login": (10, 60),  # 10/min per IP
    "facts/create": (30, 3600),  # 30/hr per user
    "facts/edit": (60, 3600),  # 60/hr per user
    "ai/chat": (150, 3600),  # 150/hr per user
    "ai/search": (60, 3600),  # 60/hr per user
    "import/upload": (10, 3600),  # 10/hr per user
    "import/analyze": (10, 3600),  # 10/hr per user
    "export/factsheet": (30, 3600),  # 30/hr per user
    "export/document": (9, 3600),  # 9/hr per user
    "feedback/submit": (1, 60),  # 1/min per IP
}

# Legacy fallback
DEFAULT_LIMITS: dict[str, int] = {
    "login": 10,
    "api_read": 200,
    "api_write": 50,
}

WINDOW_SECONDS = 3600


async def check_rate(identifier: str, action: str) -> None:
    """Increment rate counter and raise 429 if threshold exceeded."""
    r = await get_redis()

    if action in RATE_LIMITS:
        limit, window = RATE_LIMITS[action]
    else:
        limit = DEFAULT_LIMITS.get(action, 100)
        window = WINDOW_SECONDS

    key = f"rate:{action}:{identifier}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, window)
    if count > limit:
        raise RateLimited(f"Rate limit exceeded for {action}")
