"""Auth middleware unit tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from artiFACT.main import app


@pytest.mark.asyncio
async def test_unauthenticated_returns_401() -> None:
    """Unauthenticated requests to protected endpoints should return 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/users/me")
        assert response.status_code == 401
