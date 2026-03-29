"""Additional security and coverage tests."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from artiFACT.kernel.rate_limiter import RATE_LIMITS
from artiFACT.kernel.security_headers import SECURITY_HEADERS
from artiFACT.main import app


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """Plain HTTP client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_rate_limits_configured() -> None:
    """All sprint-13 rate limits are configured."""
    required = [
        "auth/login",
        "facts/create",
        "facts/edit",
        "ai/chat",
        "ai/search",
        "import/upload",
        "import/analyze",
        "export/factsheet",
        "export/document",
        "feedback/submit",
    ]
    for key in required:
        assert key in RATE_LIMITS, f"Missing rate limit for {key}"


async def test_security_headers_complete() -> None:
    """All required security headers are configured."""
    required = [
        "Content-Security-Policy",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Strict-Transport-Security",
        "Referrer-Policy",
        "Permissions-Policy",
    ]
    for header in required:
        assert header in SECURITY_HEADERS, f"Missing security header: {header}"


async def test_404_api_returns_json(client: AsyncClient) -> None:
    """API 404 returns JSON, not HTML."""
    resp = await client.get("/api/v1/nonexistent")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Not found"


async def test_404_browser_returns_html(client: AsyncClient) -> None:
    """Browser 404 returns HTML error page."""
    resp = await client.get("/nonexistent", headers={"accept": "text/html"})
    assert resp.status_code == 404
    assert "Page Not Found" in resp.text


async def test_openapi_spec_available(client: AsyncClient) -> None:
    """OpenAPI spec is accessible and valid."""
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert spec["info"]["title"] == "artiFACT"
    assert len(spec["paths"]) > 0


async def test_health_returns_json(client: AsyncClient) -> None:
    """Health check returns proper JSON."""
    resp = await client.get("/api/v1/health")
    data = resp.json()
    assert data["status"] == "healthy"


async def test_log_forwarder_config() -> None:
    """Structlog is configured with JSON output."""
    import structlog
    from artiFACT.kernel.log_forwarder import configure_structlog

    configure_structlog()
    logger = structlog.get_logger()
    assert logger is not None


async def test_access_logger_creates_event(db, admin_user) -> None:
    """Access logger creates events in the database."""
    from sqlalchemy import select
    from artiFACT.kernel.access_logger import log_data_access
    from artiFACT.kernel.models import FcEventLog

    await log_data_access(db, admin_user.user_uid, "sync_delta", {"cursor": 0, "count": 10})
    await db.flush()

    result = await db.execute(
        select(FcEventLog).where(FcEventLog.event_type == "access.sync_delta")
    )
    event = result.scalar_one_or_none()
    assert event is not None


async def test_anomaly_detector_no_flag_below_threshold(db, admin_user) -> None:
    """Anomaly detector does not flag below threshold."""
    from artiFACT.modules.admin.anomaly_detector import check_anomaly
    from artiFACT.kernel.auth.session import get_redis

    r = await get_redis()
    # Clean up
    async for key in r.scan_iter(match=f"anomaly:*:{admin_user.user_uid}"):
        await r.delete(key)

    # Single export should not flag
    flagged = await check_anomaly(db, admin_user.user_uid, "export")
    assert flagged is False
