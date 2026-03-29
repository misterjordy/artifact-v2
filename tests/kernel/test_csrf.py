"""CSRF middleware unit tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from artiFACT.kernel.auth.csrf import generate_csrf_token
from artiFACT.main import app


@pytest.mark.asyncio
async def test_csrf_required_on_post() -> None:
    """POST requests (except exempt paths) should require CSRF token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_csrf_not_required_on_get() -> None:
    """GET requests should not require CSRF token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
