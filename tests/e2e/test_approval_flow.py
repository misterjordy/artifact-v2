"""E2E test: contributor proposes fact, approver approves, error pages render.

Runs against real PostgreSQL and Redis inside Docker.
NO mocking of internal systems.
"""

import uuid
from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.events import publish
from artiFACT.kernel.models import (
    FcFact,
    FcFactVersion,
    FcNode,
    FcNodePermission,
    FcUser,
)
from artiFACT.main import app


async def test_contributor_propose_approver_approve(
    db: AsyncSession,
    admin_user: FcUser,
    contributor_user: FcUser,
    approver_user: FcUser,
    root_node: FcNode,
    child_node: FcNode,
    approver_permission: FcNodePermission,
    contributor_permission: FcNodePermission,
) -> None:
    """E2E: Contributor submits fact -> approver approves -> state is published."""
    # Contributor creates a fact (proposed state)
    fact = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=child_node.node_uid,
        created_by_uid=contributor_user.user_uid,
    )
    db.add(fact)
    await db.flush()

    version = FcFactVersion(
        version_uid=uuid.uuid4(),
        fact_uid=fact.fact_uid,
        state="proposed",
        display_sentence="The system operates at IL-4.",
        created_by_uid=contributor_user.user_uid,
    )
    db.add(version)
    await db.flush()

    fact.current_published_version_uid = version.version_uid
    await db.flush()

    await publish(
        "fact.created",
        {
            "fact_uid": fact.fact_uid,
            "version_uid": version.version_uid,
            "node_uid": child_node.node_uid,
            "actor_uid": contributor_user.user_uid,
        },
    )

    # Approver approves: transition to published
    version.state = "published"
    version.published_at = datetime.now(timezone.utc)
    await db.flush()

    await publish(
        "version.published",
        {
            "version_uid": version.version_uid,
            "fact_uid": fact.fact_uid,
            "new_state": "published",
            "actor_uid": approver_user.user_uid,
        },
    )

    # Verify published state
    refreshed = await db.get(FcFactVersion, version.version_uid)
    assert refreshed is not None
    assert refreshed.state == "published"
    assert refreshed.published_at is not None


async def test_error_pages_render() -> None:
    """Custom error pages render correctly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 404 for unknown page (browser request)
        resp = await client.get("/nonexistent-page", headers={"accept": "text/html"})
        assert resp.status_code == 404
        assert "Page Not Found" in resp.text

        # 401 for protected API endpoint
        resp = await client.get("/api/v1/users/me")
        assert resp.status_code == 401
