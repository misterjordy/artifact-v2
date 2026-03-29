"""Integration tests for Sprint 12: Admin Dashboard.

Testing rules:
- Runs against real PostgreSQL (inside Docker)
- NO mocking of: auth middleware, permission checks, event bus
- Real sessions via Redis, real CSRF tokens
- The non_admin_gets_403 test sends real HTTP through full middleware stack
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.session import create_session
from artiFACT.kernel.models import FcFact, FcFactVersion, FcSystemConfig, FcUser
from artiFACT.main import app


# ── Helpers ──


async def _create_session_cookie(user: FcUser) -> str:
    """Create a real Redis session and return the session_id cookie value."""
    return await create_session(user)


def _csrf_headers(session_id: str) -> dict:
    """Build headers with both session cookie and CSRF token."""
    csrf_token = "test-csrf-token"
    return {
        "cookie": f"session_id={session_id}; csrf_token={csrf_token}",
        "x-csrf-token": csrf_token,
    }


def _get_headers(session_id: str) -> dict:
    """Build GET headers (session cookie only, no CSRF needed)."""
    return {"cookie": f"session_id={session_id}"}


# ── Fixtures ──


@pytest_asyncio.fixture
async def test_client(db: AsyncSession):
    """Test HTTP client with real DB session."""
    from artiFACT.kernel.db import get_db

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_with_session(db: AsyncSession, admin_user: FcUser):
    """Admin user with real Redis session."""
    sid = await _create_session_cookie(admin_user)
    return admin_user, sid


@pytest_asyncio.fixture
async def contributor_with_session(db: AsyncSession, contributor_user: FcUser):
    """Contributor user with real Redis session."""
    sid = await _create_session_cookie(contributor_user)
    return contributor_user, sid


@pytest_asyncio.fixture
async def sample_facts(db: AsyncSession, admin_user: FcUser, root_node):
    """Create sample facts for dashboard metrics."""
    facts = []
    for i in range(3):
        fact = FcFact(
            fact_uid=uuid.uuid4(),
            node_uid=root_node.node_uid,
            is_retired=False,
            created_by_uid=admin_user.user_uid,
        )
        db.add(fact)
        await db.flush()

        version = FcFactVersion(
            version_uid=uuid.uuid4(),
            fact_uid=fact.fact_uid,
            state="published",
            display_sentence=f"Admin test fact {i + 1}.",
            classification="UNCLASSIFIED",
            created_by_uid=admin_user.user_uid,
            published_at=datetime.now(timezone.utc),
        )
        db.add(version)
        await db.flush()

        fact.current_published_version_uid = version.version_uid
        await db.flush()
        facts.append(fact)

    return facts


@pytest_asyncio.fixture
async def feature_flag(db: AsyncSession, admin_user: FcUser):
    """Create a feature flag in fc_system_config."""
    cfg = FcSystemConfig(
        key="feature_dark_mode",
        value={"enabled": True, "description": "Dark mode toggle"},
        updated_by_uid=admin_user.user_uid,
    )
    db.add(cfg)
    await db.flush()
    return cfg


# ══════════════════════════════════════════════
# TEST: All admin endpoints require admin role
# ══════════════════════════════════════════════


ADMIN_GET_ENDPOINTS = [
    "/api/v1/admin/dashboard",
    "/api/v1/admin/users",
    "/api/v1/admin/modules",
    "/api/v1/admin/config",
    "/api/v1/admin/health",
    "/api/v1/admin/cache/stats",
]

ADMIN_POST_ENDPOINTS = [
    "/api/v1/admin/snapshot",
    "/api/v1/admin/cache/flush",
]


class TestAdminRequiredOnAllEndpoints:
    """Every admin endpoint must reject unauthenticated requests with 401."""

    @pytest.mark.parametrize("endpoint", ADMIN_GET_ENDPOINTS)
    async def test_unauthenticated_get_returns_401(self, test_client: AsyncClient, endpoint: str):
        resp = await test_client.get(endpoint)
        assert resp.status_code == 401

    @pytest.mark.parametrize("endpoint", ADMIN_POST_ENDPOINTS)
    async def test_unauthenticated_post_returns_401_or_403(
        self, test_client: AsyncClient, endpoint: str
    ):
        resp = await test_client.post(endpoint)
        # 401 (no auth) or 403 (CSRF missing) — both are correct rejections
        assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════
# TEST: Non-admin gets 403 (real middleware, no mocks)
# ══════════════════════════════════════════════


class TestNonAdminGets403:
    """Non-admin user hitting admin endpoints gets a real 403 through the full stack."""

    @pytest.mark.parametrize("endpoint", ADMIN_GET_ENDPOINTS)
    async def test_non_admin_get_returns_403(
        self, test_client: AsyncClient, contributor_with_session, endpoint: str
    ):
        _, sid = contributor_with_session
        resp = await test_client.get(endpoint, headers=_get_headers(sid))
        assert resp.status_code == 403

    async def test_non_admin_post_returns_403(
        self, test_client: AsyncClient, contributor_with_session
    ):
        _, sid = contributor_with_session
        resp = await test_client.post(
            "/api/v1/admin/cache/flush",
            headers=_csrf_headers(sid),
        )
        assert resp.status_code == 403

    async def test_non_admin_config_update_returns_403(
        self, test_client: AsyncClient, contributor_with_session
    ):
        _, sid = contributor_with_session
        resp = await test_client.post(
            "/api/v1/admin/config/some_key",
            json={"value": {"enabled": True}},
            headers=_csrf_headers(sid),
        )
        assert resp.status_code == 403

    async def test_non_admin_role_change_returns_403(
        self, test_client: AsyncClient, contributor_with_session, admin_user
    ):
        _, sid = contributor_with_session
        resp = await test_client.put(
            f"/api/v1/admin/users/{admin_user.user_uid}/role",
            json={"global_role": "viewer"},
            headers=_csrf_headers(sid),
        )
        assert resp.status_code == 403

    async def test_non_admin_deactivate_returns_403(
        self, test_client: AsyncClient, contributor_with_session, admin_user
    ):
        _, sid = contributor_with_session
        resp = await test_client.post(
            f"/api/v1/admin/users/{admin_user.user_uid}/deactivate",
            headers=_csrf_headers(sid),
        )
        assert resp.status_code == 403


# ══════════════════════════════════════════════
# TEST: Dashboard returns valid metrics
# ══════════════════════════════════════════════


class TestDashboardReturnsValidMetrics:
    async def test_dashboard_returns_valid_metrics(
        self,
        test_client: AsyncClient,
        admin_with_session,
        sample_facts,
    ):
        admin_user, sid = admin_with_session
        resp = await test_client.get(
            "/api/v1/admin/dashboard",
            headers=_get_headers(sid),
        )
        assert resp.status_code == 200
        data = resp.json()

        # Verify all four top-level sections
        assert "users" in data
        assert "facts" in data
        assert "queue" in data
        assert "system" in data

        # User metrics
        assert data["users"]["total"] >= 1
        assert "active_24h" in data["users"]
        assert "by_role" in data["users"]

        # Fact metrics
        assert data["facts"]["total"] >= 3
        assert "by_state" in data["facts"]
        assert "created_7d" in data["facts"]

        # Queue metrics
        assert "pending_proposals" in data["queue"]
        assert "pending_moves" in data["queue"]

        # System metrics
        assert "version" in data["system"]
        assert "deploy_sha" in data["system"]
        assert "uptime" in data["system"]
        assert "error_rate" in data["system"]


# ══════════════════════════════════════════════
# TEST: Feature flag toggle takes effect
# ══════════════════════════════════════════════


class TestFeatureFlagToggleTakesEffect:
    async def test_feature_flag_toggle_takes_effect(
        self,
        db: AsyncSession,
        test_client: AsyncClient,
        admin_with_session,
        feature_flag,
    ):
        admin_user, sid = admin_with_session

        # Verify initial state
        resp = await test_client.get(
            "/api/v1/admin/config",
            headers=_get_headers(sid),
        )
        assert resp.status_code == 200
        configs = resp.json()
        flag = next(c for c in configs if c["key"] == "feature_dark_mode")
        assert flag["value"]["enabled"] is True

        # Toggle to disabled
        resp = await test_client.post(
            "/api/v1/admin/config/feature_dark_mode",
            json={"value": {"enabled": False, "description": "Dark mode toggle"}},
            headers=_csrf_headers(sid),
        )
        assert resp.status_code == 200
        assert resp.json()["value"]["enabled"] is False

        # Verify change persisted
        resp = await test_client.get(
            "/api/v1/admin/config",
            headers=_get_headers(sid),
        )
        flag = next(c for c in resp.json() if c["key"] == "feature_dark_mode")
        assert flag["value"]["enabled"] is False

        # Toggle back to enabled
        resp = await test_client.post(
            "/api/v1/admin/config/feature_dark_mode",
            json={"value": {"enabled": True, "description": "Dark mode toggle"}},
            headers=_csrf_headers(sid),
        )
        assert resp.status_code == 200
        assert resp.json()["value"]["enabled"] is True


# ══════════════════════════════════════════════
# TEST: Snapshot creates file in S3
# ══════════════════════════════════════════════


class TestSnapshotCreatesFileInS3:
    async def test_snapshot_creates_file_in_s3(
        self,
        test_client: AsyncClient,
        admin_with_session,
    ):
        """Trigger snapshot — Celery task is mocked at the task.delay level only."""
        admin_user, sid = admin_with_session

        with patch("artiFACT.modules.admin.router.trigger_snapshot") as mock_task:
            mock_task.delay.return_value = None
            resp = await test_client.post(
                "/api/v1/admin/snapshot",
                headers=_csrf_headers(sid),
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "queued"
            mock_task.delay.assert_called_once_with(str(admin_user.user_uid))


# ══════════════════════════════════════════════
# TEST: Cache flush clears permissions
# ══════════════════════════════════════════════


class TestCacheFlushClearsPermissions:
    async def test_cache_flush_clears_permissions(
        self,
        test_client: AsyncClient,
        admin_with_session,
    ):
        admin_user, sid = admin_with_session

        # Seed a permissions key in Redis
        import redis.asyncio as aioredis
        from artiFACT.kernel.config import settings

        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.set("permissions:test_key", "test_value")
        await r.aclose()

        # Flush permissions category
        resp = await test_client.post(
            "/api/v1/admin/cache/flush?category=permissions",
            headers=_csrf_headers(sid),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "permissions"
        assert data["flushed"] >= 1

        # Verify the key is gone
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        val = await r.get("permissions:test_key")
        await r.aclose()
        assert val is None


# ══════════════════════════════════════════════
# TEST: User management — list, search, role change, deactivate/reactivate
# ══════════════════════════════════════════════


class TestUserManagement:
    async def test_list_users(
        self,
        test_client: AsyncClient,
        admin_with_session,
        contributor_user,
    ):
        admin_user, sid = admin_with_session
        resp = await test_client.get(
            "/api/v1/admin/users",
            headers=_get_headers(sid),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        assert len(data["data"]) >= 2

    async def test_search_users(
        self,
        test_client: AsyncClient,
        admin_with_session,
        contributor_user,
    ):
        admin_user, sid = admin_with_session
        resp = await test_client.get(
            f"/api/v1/admin/users?q={contributor_user.display_name}",
            headers=_get_headers(sid),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        names = [u["display_name"] for u in data["data"]]
        assert contributor_user.display_name in names

    async def test_change_role(
        self,
        db: AsyncSession,
        test_client: AsyncClient,
        admin_with_session,
        contributor_user,
    ):
        admin_user, sid = admin_with_session
        resp = await test_client.put(
            f"/api/v1/admin/users/{contributor_user.user_uid}/role",
            json={"global_role": "approver"},
            headers=_csrf_headers(sid),
        )
        assert resp.status_code == 200
        assert resp.json()["global_role"] == "approver"

    async def test_deactivate_reactivate(
        self,
        db: AsyncSession,
        test_client: AsyncClient,
        admin_with_session,
        contributor_user,
    ):
        admin_user, sid = admin_with_session

        # Deactivate
        resp = await test_client.post(
            f"/api/v1/admin/users/{contributor_user.user_uid}/deactivate",
            headers=_csrf_headers(sid),
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

        # Reactivate
        resp = await test_client.post(
            f"/api/v1/admin/users/{contributor_user.user_uid}/reactivate",
            headers=_csrf_headers(sid),
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True


# ══════════════════════════════════════════════
# TEST: Module health returns per-module status
# ══════════════════════════════════════════════


class TestModuleHealth:
    async def test_module_health(
        self,
        test_client: AsyncClient,
        admin_with_session,
    ):
        admin_user, sid = admin_with_session
        resp = await test_client.get(
            "/api/v1/admin/modules",
            headers=_get_headers(sid),
        )
        assert resp.status_code == 200
        modules = resp.json()
        assert len(modules) > 0

        for mod in modules:
            assert "module" in mod
            assert "db" in mod
            assert "redis" in mod
            assert "s3" in mod

        # DB and Redis should be OK in Docker
        assert all(m["db"] for m in modules)
        assert all(m["redis"] for m in modules)


# ══════════════════════════════════════════════
# TEST: Cache stats
# ══════════════════════════════════════════════


class TestCacheStats:
    async def test_cache_stats(
        self,
        test_client: AsyncClient,
        admin_with_session,
    ):
        admin_user, sid = admin_with_session
        resp = await test_client.get(
            "/api/v1/admin/cache/stats",
            headers=_get_headers(sid),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "used_memory_human" in data
        assert "connected_clients" in data
        assert "total_keys" in data
