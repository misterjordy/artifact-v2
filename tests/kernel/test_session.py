"""Session management unit tests."""

import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from artiFACT.kernel.auth.session import (
    SESSION_TTL,
    REVALIDATION_WINDOW,
    create_session,
    destroy_session,
    force_destroy_user_sessions,
    validate_session,
)
from artiFACT.kernel.models import FcUser


@pytest.fixture
def active_user() -> FcUser:
    return FcUser(
        user_uid=uuid.uuid4(),
        cac_dn="test-user",
        display_name="Test User",
        global_role="viewer",
        is_active=True,
    )


@pytest.fixture
def deactivated_user() -> FcUser:
    return FcUser(
        user_uid=uuid.uuid4(),
        cac_dn="deactivated",
        display_name="Deactivated User",
        global_role="viewer",
        is_active=False,
    )


@pytest.mark.asyncio
async def test_session_creation_and_retrieval(active_user: FcUser) -> None:
    """Creating a session should store it in Redis and be retrievable."""
    mock_redis = AsyncMock()
    mock_redis.setex.return_value = True

    with patch("artiFACT.kernel.auth.session.get_redis", return_value=mock_redis):
        session_id = await create_session(active_user)

    assert session_id is not None
    assert len(session_id) == 36  # UUID format
    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert call_args[0][1] == SESSION_TTL


@pytest.mark.asyncio
async def test_session_expiry() -> None:
    """An expired session (not in Redis) should return None."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None  # Session expired / not found

    db = AsyncMock()

    with patch("artiFACT.kernel.auth.session.get_redis", return_value=mock_redis):
        result = await validate_session("nonexistent-session-id", db)

    assert result is None


@pytest.mark.asyncio
async def test_session_revalidation_catches_deactivated_user(
    deactivated_user: FcUser,
) -> None:
    """ZT continuous auth: deactivated user should be caught during revalidation."""
    mock_redis = AsyncMock()
    # Session exists but last_validated_at is old (>15 min)
    old_time = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    session_data = json.dumps({
        "user_uid": str(deactivated_user.user_uid),
        "cac_dn": deactivated_user.cac_dn,
        "last_validated_at": old_time,
    })
    mock_redis.get.return_value = session_data
    mock_redis.delete.return_value = True

    # DB returns the deactivated user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = deactivated_user
    db = AsyncMock()
    db.execute.return_value = mock_result

    with patch("artiFACT.kernel.auth.session.get_redis", return_value=mock_redis):
        result = await validate_session("some-session-id", db)

    assert result is None
    # Session should have been destroyed
    mock_redis.delete.assert_called_once()


@pytest.mark.asyncio
async def test_session_revalidation_within_15min_window(active_user: FcUser) -> None:
    """ZT: within 15min window, session should validate without re-checking DB for active status."""
    mock_redis = AsyncMock()
    # Session exists, last_validated_at is recent (<15 min)
    recent_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    session_data = json.dumps({
        "user_uid": str(active_user.user_uid),
        "cac_dn": active_user.cac_dn,
        "last_validated_at": recent_time,
    })
    mock_redis.get.return_value = session_data

    # DB returns the user (for the basic lookup, not revalidation)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = active_user
    db = AsyncMock()
    db.execute.return_value = mock_result

    with patch("artiFACT.kernel.auth.session.get_redis", return_value=mock_redis):
        result = await validate_session("some-session-id", db)

    assert result is not None
    assert result.user_uid == active_user.user_uid


@pytest.mark.asyncio
async def test_force_destroy_kills_all_user_sessions(active_user: FcUser) -> None:
    """ZT auto-remediation: force_destroy should delete all sessions for a user."""
    user_uid = active_user.user_uid
    session_data_match = json.dumps({
        "user_uid": str(user_uid),
        "cac_dn": "test-user",
        "last_validated_at": datetime.now(timezone.utc).isoformat(),
    })
    session_data_other = json.dumps({
        "user_uid": str(uuid.uuid4()),
        "cac_dn": "other-user",
        "last_validated_at": datetime.now(timezone.utc).isoformat(),
    })

    mock_redis = AsyncMock()
    # scan_iter returns an async iterable (not a coroutine)
    mock_redis.scan_iter = lambda **kwargs: AsyncIterableKeys(
        ["session:aaa", "session:bbb", "session:ccc"]
    )
    # get returns data for each key
    mock_redis.get.side_effect = [
        session_data_match,
        session_data_other,
        session_data_match,
    ]
    mock_redis.delete.return_value = True

    with patch("artiFACT.kernel.auth.session.get_redis", return_value=mock_redis):
        count = await force_destroy_user_sessions(user_uid)

    assert count == 2  # Only the 2 matching sessions
    assert mock_redis.delete.call_count == 2


class AsyncIterableKeys:
    """Helper to mock async iterator for redis scan_iter."""

    def __init__(self, keys: list[str]) -> None:
        self._keys = keys

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        if not self._keys:
            raise StopAsyncIteration
        return self._keys.pop(0)
