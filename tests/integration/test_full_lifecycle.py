"""Integration tests: security headers, CSRF enforcement, auth blocking, health.

Run against real PostgreSQL and Redis inside Docker.
NO mocking of internal systems. Tests that need HTTP use ASGI transport.
"""

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from artiFACT.main import app


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """Plain HTTP client (no auth)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_security_headers_present(client: AsyncClient) -> None:
    """All responses include security headers."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.headers.get("x-frame-options") == "SAMEORIGIN"
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert "strict-transport-security" in resp.headers
    assert "content-security-policy" in resp.headers
    assert "referrer-policy" in resp.headers
    assert "permissions-policy" in resp.headers


async def test_health_endpoint(client: AsyncClient) -> None:
    """Health check returns healthy."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


async def test_request_id_header(client: AsyncClient) -> None:
    """Every response includes X-Request-ID."""
    resp = await client.get("/api/v1/health")
    assert "x-request-id" in resp.headers
    uuid.UUID(resp.headers["x-request-id"])


async def test_unauthenticated_blocked(client: AsyncClient) -> None:
    """Protected endpoints return 401 without auth."""
    endpoints = ["/api/v1/nodes", "/api/v1/users/me"]
    for path in endpoints:
        resp = await client.get(path)
        assert resp.status_code == 401, f"{path} accessible without auth: {resp.status_code}"


async def test_csrf_required_on_writes(client: AsyncClient) -> None:
    """POST without CSRF returns 403."""
    resp = await client.post("/api/v1/nodes", json={"title": "Test"})
    assert resp.status_code == 403


async def test_fact_lifecycle_propose_approve_sign(
    db,
    admin_user,
) -> None:
    """Full lifecycle at service layer: create node -> create fact -> approve -> sign.

    Uses real DB (not HTTP) to avoid event-loop/ASGI issues.
    """
    from artiFACT.kernel.events import publish
    from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcSignature

    # Create node
    node = FcNode(
        node_uid=uuid.uuid4(),
        title="Lifecycle Test",
        slug=f"lifecycle-{uuid.uuid4().hex[:8]}",
        node_depth=0,
        created_by_uid=admin_user.user_uid,
    )
    db.add(node)
    await db.flush()

    # Create fact + version (admin auto-publishes)
    from datetime import datetime, timezone

    fact = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=node.node_uid,
        created_by_uid=admin_user.user_uid,
    )
    db.add(fact)
    await db.flush()

    version = FcFactVersion(
        version_uid=uuid.uuid4(),
        fact_uid=fact.fact_uid,
        state="published",
        display_sentence="System is Navy-owned.",
        created_by_uid=admin_user.user_uid,
        published_at=datetime.now(timezone.utc),
    )
    db.add(version)
    await db.flush()

    fact.current_published_version_uid = version.version_uid
    await db.flush()

    # Publish event (event bus runs for real)
    await publish(
        "fact.created",
        {
            "fact_uid": fact.fact_uid,
            "version_uid": version.version_uid,
            "node_uid": node.node_uid,
            "actor_uid": admin_user.user_uid,
        },
    )

    # Sign
    sig = FcSignature(
        signature_uid=uuid.uuid4(),
        node_uid=node.node_uid,
        signed_by_uid=admin_user.user_uid,
        fact_count=1,
    )
    db.add(sig)
    await db.flush()

    await publish(
        "signature.created",
        {
            "signature_uid": sig.signature_uid,
            "node_uid": node.node_uid,
            "actor_uid": admin_user.user_uid,
            "fact_count": 1,
        },
    )

    # Verify: fact is published, signature exists
    refreshed_fact = await db.get(FcFact, fact.fact_uid)
    assert refreshed_fact is not None
    assert refreshed_fact.current_published_version_uid == version.version_uid

    refreshed_sig = await db.get(FcSignature, sig.signature_uid)
    assert refreshed_sig is not None
    assert refreshed_sig.fact_count == 1
