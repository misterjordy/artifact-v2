"""Rate limiter unit tests."""

import pytest
from unittest.mock import AsyncMock, patch

from artiFACT.kernel.exceptions import RateLimited
from artiFACT.kernel.rate_limiter import check_rate


@pytest.mark.asyncio
async def test_rate_limiter_blocks_after_threshold() -> None:
    """Rate limiter should raise 429 after exceeding the threshold."""
    mock_redis = AsyncMock()
    # Simulate count exceeding limit (login limit = 10)
    mock_redis.incr.return_value = 11
    mock_redis.expire.return_value = True

    with patch("artiFACT.kernel.rate_limiter.get_redis", return_value=mock_redis):
        with pytest.raises(RateLimited):
            await check_rate("test-user", "login")


@pytest.mark.asyncio
async def test_rate_limiter_resets_after_window() -> None:
    """Rate limiter should allow requests after the window resets (count = 1)."""
    mock_redis = AsyncMock()
    # First request after window reset
    mock_redis.incr.return_value = 1
    mock_redis.expire.return_value = True

    with patch("artiFACT.kernel.rate_limiter.get_redis", return_value=mock_redis):
        # Should not raise
        await check_rate("test-user", "login")
        # expire should be called since count == 1
        mock_redis.expire.assert_called_once()
