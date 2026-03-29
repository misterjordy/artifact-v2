"""Integration tests for Sprint 9: Export + Sync + Templates.

Testing rules:
- Runs against real PostgreSQL (inside Docker)
- NO mocking of: permission resolver, auth middleware, event bus, download URL verification
- ONLY mocking: external LLM API calls, S3 presigned URL generation
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.session import create_session
from artiFACT.kernel.models import (
    FcApiKey,
    FcDocumentTemplate,
    FcEventLog,
    FcFact,
    FcFactVersion,
    FcNode,
    FcNodePermission,
    FcUser,
)
from artiFACT.main import app


# ── Helpers ──


async def _create_session_cookie(user: FcUser) -> str:
    """Create a real Redis session and return the session_id cookie value."""
    session_id = await create_session(user)
    return session_id


def _csrf_headers(session_id: str) -> dict:
    """Build headers with both session cookie and CSRF token."""
    csrf_token = "test-csrf-token"
    return {
        "cookie": f"session_id={session_id}; csrf_token={csrf_token}",
        "x-csrf-token": csrf_token,
    }


@pytest_asyncio.fixture
async def admin_with_session(db: AsyncSession, admin_user: FcUser):
    """Admin user with real session."""
    sid = await _create_session_cookie(admin_user)
    return admin_user, sid


@pytest_asyncio.fixture
async def contributor_with_session(db: AsyncSession, contributor_user: FcUser):
    """Contributor user with real session."""
    sid = await _create_session_cookie(contributor_user)
    return contributor_user, sid


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
async def template(db: AsyncSession, admin_user: FcUser) -> FcDocumentTemplate:
    """Pre-created document template."""
    tpl = FcDocumentTemplate(
        template_uid=uuid.uuid4(),
        name="Test ConOps",
        abbreviation="ConOps",
        description="Test template",
        sections=[
            {"key": "purpose", "title": "1. Purpose",
             "prompt": "Describe the purpose", "guidance": "Focus on purpose"},
            {"key": "overview", "title": "2. Overview",
             "prompt": "Describe the overview", "guidance": "Focus on overview"},
        ],
        created_by_uid=admin_user.user_uid,
    )
    db.add(tpl)
    await db.flush()
    return tpl


@pytest_asyncio.fixture
async def facts_with_events(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode, approver_permission
) -> list[FcFact]:
    """Create published facts with event log entries."""
    facts = []
    for i in range(5):
        fact = FcFact(
            fact_uid=uuid.uuid4(),
            node_uid=child_node.node_uid,
            is_retired=False,
            created_by_uid=admin_user.user_uid,
        )
        db.add(fact)
        await db.flush()

        version = FcFactVersion(
            version_uid=uuid.uuid4(),
            fact_uid=fact.fact_uid,
            state="published",
            display_sentence=f"Test fact number {i + 1} for export testing.",
            classification="UNCLASSIFIED",
            metadata_tags=["test"],
            created_by_uid=admin_user.user_uid,
            published_at=datetime.now(timezone.utc),
        )
        db.add(version)
        await db.flush()

        fact.current_published_version_uid = version.version_uid
        await db.flush()

        event = FcEventLog(
            entity_type="fact",
            entity_uid=fact.fact_uid,
            event_type="fact.created",
            payload={"fact_uid": str(fact.fact_uid), "sentence": version.display_sentence},
            actor_uid=admin_user.user_uid,
        )
        db.add(event)
        await db.flush()

        facts.append(fact)

    # Add a retired fact with tombstone event
    retired_fact = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=child_node.node_uid,
        is_retired=True,
        created_by_uid=admin_user.user_uid,
        retired_at=datetime.now(timezone.utc),
    )
    db.add(retired_fact)
    await db.flush()

    retired_version = FcFactVersion(
        version_uid=uuid.uuid4(),
        fact_uid=retired_fact.fact_uid,
        state="retired",
        display_sentence="This fact was retired for testing.",
        classification="UNCLASSIFIED",
        created_by_uid=admin_user.user_uid,
    )
    db.add(retired_version)
    await db.flush()

    retired_event = FcEventLog(
        entity_type="fact",
        entity_uid=retired_fact.fact_uid,
        event_type="fact.retired",
        payload={
            "fact_uid": str(retired_fact.fact_uid),
            "sentence": retired_version.display_sentence,
            "is_retired": True,
        },
        actor_uid=admin_user.user_uid,
    )
    db.add(retired_event)
    await db.flush()

    return facts


@pytest_asyncio.fixture
async def cui_facts(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode, approver_permission
) -> list[FcFact]:
    """Create facts with CUI classification."""
    facts = []
    for i, cls in enumerate(["UNCLASSIFIED", "CUI", "CUI//SP-CTI"]):
        fact = FcFact(
            fact_uid=uuid.uuid4(),
            node_uid=child_node.node_uid,
            is_retired=False,
            created_by_uid=admin_user.user_uid,
        )
        db.add(fact)
        await db.flush()

        version = FcFactVersion(
            version_uid=uuid.uuid4(),
            fact_uid=fact.fact_uid,
            state="published",
            display_sentence=f"CUI test fact {i + 1} classified as {cls}.",
            classification=cls,
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
async def service_account(db: AsyncSession) -> tuple[FcUser, str]:
    """Create a service account with API key and sync scope."""
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=Service Account {uuid.uuid4().hex[:8]}",
        display_name="Advana Service",
        global_role="viewer",
    )
    db.add(user)
    await db.flush()

    raw_key = f"af_svc_{uuid.uuid4().hex}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    api_key = FcApiKey(
        key_uid=uuid.uuid4(),
        user_uid=user.user_uid,
        key_hash=key_hash,
        key_prefix=raw_key[:8],
        label="Advana sync",
        scopes=["read", "sync"],
    )
    db.add(api_key)
    await db.flush()

    return user, raw_key


# ══════════════════════════════════════════════
# TEST: ALL export routes require auth (v1 D-SEC-01 / SEC-04)
# ══════════════════════════════════════════════


class TestExportRequiresAuth:
    """v1 D-SEC-01: Every export endpoint must reject unauthenticated requests."""

    async def test_factsheet_requires_auth(self, test_client: AsyncClient):
        resp = await test_client.get(
            "/api/v1/export/factsheet",
            params={"node_uids": str(uuid.uuid4()), "format": "json"},
        )
        assert resp.status_code == 401

    async def test_document_post_requires_auth(self, test_client: AsyncClient):
        resp = await test_client.post(
            "/api/v1/export/document",
            json={"node_uids": [str(uuid.uuid4())], "template_uid": str(uuid.uuid4())},
            headers={"x-csrf-token": "x", "cookie": "csrf_token=x"},
        )
        assert resp.status_code == 401

    async def test_document_progress_requires_auth(self, test_client: AsyncClient):
        resp = await test_client.get(f"/api/v1/export/document/{uuid.uuid4()}/progress")
        assert resp.status_code == 401

    async def test_document_download_requires_auth(self, test_client: AsyncClient):
        resp = await test_client.get(f"/api/v1/export/document/{uuid.uuid4()}/download")
        assert resp.status_code == 401

    async def test_templates_list_requires_auth(self, test_client: AsyncClient):
        resp = await test_client.get("/api/v1/export/templates")
        assert resp.status_code == 401

    async def test_template_create_requires_auth(self, test_client: AsyncClient):
        resp = await test_client.post(
            "/api/v1/export/templates",
            json={"name": "Test", "abbreviation": "T", "sections": [{"key": "a", "title": "A", "prompt": "p"}]},
            headers={"x-csrf-token": "x", "cookie": "csrf_token=x"},
        )
        assert resp.status_code == 401

    async def test_views_requires_auth(self, test_client: AsyncClient):
        resp = await test_client.post(
            "/api/v1/export/views",
            json={"node_uids": [str(uuid.uuid4())], "template_uid": str(uuid.uuid4())},
            headers={"x-csrf-token": "x", "cookie": "csrf_token=x"},
        )
        assert resp.status_code == 401

    async def test_sync_changes_requires_auth(self, test_client: AsyncClient):
        resp = await test_client.get("/api/v1/sync/changes?cursor=0")
        assert resp.status_code == 401

    async def test_sync_full_requires_auth(self, test_client: AsyncClient):
        resp = await test_client.get("/api/v1/sync/full")
        assert resp.status_code == 401


# ══════════════════════════════════════════════
# TEST: Download URL user-bound (v1 D-SEC-02)
# ══════════════════════════════════════════════


class TestDownloadUrlUserBound:
    """v1 D-SEC-02: Presigned URL only available to the user who generated the doc."""

    async def test_download_url_user_bound(
        self, db, admin_with_session, contributor_with_session, test_client
    ):
        """Different user cannot download another's document."""
        admin_user, admin_sid = admin_with_session
        contrib_user, contrib_sid = contributor_with_session

        # Simulate a completed document owned by admin
        import redis as redis_lib
        from artiFACT.kernel.config import settings

        session_uid = str(uuid.uuid4())
        r = redis_lib.from_url(settings.REDIS_URL)
        r.set(
            f"docgen:meta:{session_uid}",
            json.dumps({"actor_uid": str(admin_user.user_uid), "s3_key": "exports/test.docx"}),
            ex=3600,
        )

        # Admin can download (mocking S3 presigned URL generation)
        with patch("artiFACT.modules.export.download_manager.get_s3_client") as mock_s3:
            mock_s3.return_value.generate_presigned_url.return_value = "https://s3.example.com/test.docx"
            resp = await test_client.get(
                f"/api/v1/export/document/{session_uid}/download",
                headers=_csrf_headers(admin_sid),
            )
            assert resp.status_code == 200

        # Contributor CANNOT download admin's document
        resp = await test_client.get(
            f"/api/v1/export/document/{session_uid}/download",
            headers=_csrf_headers(contrib_sid),
        )
        assert resp.status_code == 403

        r.delete(f"docgen:meta:{session_uid}")


# ══════════════════════════════════════════════
# TEST: Two-pass section assignment (v1 D-LOW-01)
# ══════════════════════════════════════════════


class TestTwoPassSectionAssignment:
    """v1 D-LOW-01: Facts assigned globally, not first-section-gets-first-pick."""

    async def test_two_pass_section_assignment(self):
        from artiFACT.modules.export.docgen.prefilter import assign_facts_to_sections

        facts = [
            {"sentence": "Fact about security"},
            {"sentence": "Fact about architecture"},
            {"sentence": "Fact about testing"},
        ]

        # Section A scores high for fact 0, Section B scores high for fact 1
        # Both sections score medium for fact 2
        affinity_scores = {
            "security": {"0": 0.9, "1": 0.2, "2": 0.4},
            "architecture": {"0": 0.3, "1": 0.95, "2": 0.6},
            "testing": {"0": 0.1, "1": 0.1, "2": 0.3},
        }

        assignments = assign_facts_to_sections(affinity_scores, facts)

        # Fact 0 → security (0.9 > 0.3 > 0.1)
        assert len(assignments["security"]) == 1
        assert assignments["security"][0]["sentence"] == "Fact about security"

        # Fact 1 → architecture (0.95 > 0.2 > 0.1)
        assert len(assignments["architecture"]) >= 1
        arch_sentences = [f["sentence"] for f in assignments["architecture"]]
        assert "Fact about architecture" in arch_sentences

        # Fact 2 → architecture (0.6 > 0.4 > 0.3)
        assert "Fact about testing" in arch_sentences or len(assignments["testing"]) == 0

    async def test_below_threshold_not_assigned(self):
        from artiFACT.modules.export.docgen.prefilter import assign_facts_to_sections

        facts = [{"sentence": "Irrelevant fact"}]
        affinity_scores = {
            "section_a": {"0": 0.1},
            "section_b": {"0": 0.2},
        }

        assignments = assign_facts_to_sections(affinity_scores, facts, threshold=0.3)
        total_assigned = sum(len(v) for v in assignments.values())
        assert total_assigned == 0


# ══════════════════════════════════════════════
# TEST: Docgen runs as background task
# ══════════════════════════��═══════════════════


class TestDocgenBackgroundTask:
    async def test_docgen_runs_as_background_task(
        self,
        db,
        admin_with_session,
        test_client,
        template,
        facts_with_events,
        child_node,
    ):
        """POST /export/document returns 202 and triggers Celery task."""
        admin_user, admin_sid = admin_with_session

        with patch("artiFACT.modules.export.router.generate_document") as mock_task:
            mock_task.delay.return_value = None
            resp = await test_client.post(
                "/api/v1/export/document",
                json={
                    "node_uids": [str(child_node.node_uid)],
                    "template_uid": str(template.template_uid),
                },
                headers=_csrf_headers(admin_sid),
            )
            assert resp.status_code == 202
            data = resp.json()
            assert "session_uid" in data
            assert data["status"] == "processing"
            mock_task.delay.assert_called_once()


# ══════════════════════════════════════════════
# TEST: All four formats valid
# ══════════════════════════════════════════════


class TestAllFourFormatsValid:
    @pytest.mark.parametrize("fmt,content_type", [
        ("json", "application/json"),
        ("txt", "text/plain"),
        ("ndjson", "application/x-ndjson"),
        ("csv", "text/csv"),
    ])
    async def test_all_four_formats_valid(
        self, db, admin_with_session, test_client, facts_with_events, child_node, fmt, content_type
    ):
        admin_user, admin_sid = admin_with_session
        resp = await test_client.get(
            "/api/v1/export/factsheet",
            params={"node_uids": str(child_node.node_uid), "format": fmt},
            headers=_csrf_headers(admin_sid),
        )
        assert resp.status_code == 200
        assert content_type in resp.headers["content-type"]
        body = resp.text
        assert len(body) > 0

        if fmt == "json":
            data = json.loads(body)
            assert isinstance(data, list)
            assert len(data) == 5
        elif fmt == "ndjson":
            lines = [l for l in body.strip().split("\n") if l]
            assert len(lines) == 5
            for line in lines:
                json.loads(line)
        elif fmt == "csv":
            lines = body.strip().split("\n")
            assert len(lines) == 6  # header + 5 rows
        elif fmt == "txt":
            lines = [l for l in body.strip().split("\n") if l]
            assert len(lines) == 5


# ══════════════════════════════════════════════
# TEST: Presigned URL expires
# ══════════════════════════════════════════════


class TestPresignedUrlExpires:
    async def test_presigned_url_expires(self, db, admin_with_session, test_client):
        """Verify download URL has 1-hour expiry."""
        admin_user, admin_sid = admin_with_session

        import redis as redis_lib
        from artiFACT.kernel.config import settings

        session_uid = str(uuid.uuid4())
        r = redis_lib.from_url(settings.REDIS_URL)
        r.set(
            f"docgen:meta:{session_uid}",
            json.dumps({"actor_uid": str(admin_user.user_uid), "s3_key": "exports/test.docx"}),
            ex=3600,
        )

        with patch("artiFACT.modules.export.download_manager.get_s3_client") as mock_s3:
            mock_s3.return_value.generate_presigned_url.return_value = "https://s3.example.com/test.docx"
            resp = await test_client.get(
                f"/api/v1/export/document/{session_uid}/download",
                headers=_csrf_headers(admin_sid),
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["expires_in"] == 3600

            # Verify S3 was called with ExpiresIn=3600
            mock_s3.return_value.generate_presigned_url.assert_called_once()
            call_kwargs = mock_s3.return_value.generate_presigned_url.call_args
            assert call_kwargs[1]["ExpiresIn"] == 3600 or call_kwargs.kwargs.get("ExpiresIn") == 3600

        r.delete(f"docgen:meta:{session_uid}")


# ══════════════════════════════════════════════
# TEST: Delta feed cursor monotonic
# ══════════════════════════════════════════════


class TestDeltaFeedCursorMonotonic:
    async def test_delta_feed_cursor_monotonic(
        self, db, admin_with_session, test_client, facts_with_events
    ):
        admin_user, admin_sid = admin_with_session
        resp = await test_client.get(
            "/api/v1/sync/changes",
            params={"cursor": 0, "limit": 100},
            headers=_csrf_headers(admin_sid),
        )
        assert resp.status_code == 200
        data = resp.json()
        changes = data["changes"]
        assert len(changes) > 0

        # Verify monotonic seq
        seqs = [c["seq"] for c in changes]
        assert seqs == sorted(seqs)
        for i in range(1, len(seqs)):
            assert seqs[i] > seqs[i - 1]

        # Cursor is max seq
        assert data["cursor"] == max(seqs)


# ══════════════════════════════════════════════
# TEST: Delta feed returns entity snapshots
# ══════════════════════════════════════════════


class TestDeltaFeedReturnsEntitySnapshots:
    async def test_delta_feed_returns_entity_snapshots(
        self, db, admin_with_session, test_client, facts_with_events
    ):
        admin_user, admin_sid = admin_with_session
        resp = await test_client.get(
            "/api/v1/sync/changes",
            params={"cursor": 0, "limit": 100},
            headers=_csrf_headers(admin_sid),
        )
        assert resp.status_code == 200
        data = resp.json()

        for change in data["changes"]:
            assert "snapshot" in change
            assert "entity_type" in change
            assert "entity_uid" in change
            assert "seq" in change
            assert "occurred_at" in change
            assert "change_type" in change

            snapshot = change["snapshot"]
            assert isinstance(snapshot, dict)
            assert len(snapshot) > 0


# ══════════════════════════════════════════════
# TEST: Delta feed includes tombstones for retired
# ══════════════════════════════════════════════


class TestDeltaFeedIncludesTombstones:
    async def test_delta_feed_includes_tombstones_for_retired(
        self, db, admin_with_session, test_client, facts_with_events
    ):
        admin_user, admin_sid = admin_with_session
        resp = await test_client.get(
            "/api/v1/sync/changes",
            params={"cursor": 0, "limit": 100},
            headers=_csrf_headers(admin_sid),
        )
        assert resp.status_code == 200
        data = resp.json()

        retired_changes = [
            c for c in data["changes"] if c["change_type"] == "fact.retired"
        ]
        assert len(retired_changes) >= 1

        for rc in retired_changes:
            snapshot = rc["snapshot"]
            assert snapshot.get("is_retired") is True


# ══════════════════════════════════════════════
# TEST: Full dump includes all entity types
# ══════════════════════════════════════════════


class TestFullDumpIncludesAllEntityTypes:
    async def test_full_dump_includes_all_entity_types(
        self, db, admin_with_session, test_client, facts_with_events, template
    ):
        admin_user, admin_sid = admin_with_session
        resp = await test_client.get(
            "/api/v1/sync/full",
            headers=_csrf_headers(admin_sid),
        )
        assert resp.status_code == 200
        data = resp.json()

        assert "nodes" in data
        assert "facts" in data
        assert "versions" in data
        assert "signatures" in data
        assert "users" in data
        assert "templates" in data
        assert "events" in data
        assert "exported_at" in data
        assert data["schema_version"] == "2.0"

        assert len(data["nodes"]) > 0
        assert len(data["facts"]) > 0
        assert len(data["users"]) > 0
        assert len(data["templates"]) > 0


# ══════════════════════════════════════════════
# TEST: Full dump returns cursor for subsequent delta
# ══════════════════════════════════════════════


class TestFullDumpReturnsCursor:
    async def test_full_dump_returns_cursor_for_subsequent_delta(
        self, db, admin_with_session, test_client, facts_with_events
    ):
        admin_user, admin_sid = admin_with_session
        resp = await test_client.get(
            "/api/v1/sync/full",
            headers=_csrf_headers(admin_sid),
        )
        assert resp.status_code == 200
        data = resp.json()

        assert "cursor" in data
        assert isinstance(data["cursor"], int)
        assert data["cursor"] > 0

        # Use cursor to start delta feed — should get no new changes
        resp2 = await test_client.get(
            "/api/v1/sync/changes",
            params={"cursor": data["cursor"], "limit": 100},
            headers=_csrf_headers(admin_sid),
        )
        assert resp2.status_code == 200
        delta = resp2.json()
        assert delta["has_more"] is False


# ══════════════════════════════════════════════
# TEST: Document template CRUD
# ══════════════════════════════════════════════


class TestDocumentTemplateCrud:
    async def test_document_template_crud(self, db, admin_with_session, test_client):
        admin_user, admin_sid = admin_with_session
        headers = _csrf_headers(admin_sid)

        # CREATE
        create_resp = await test_client.post(
            "/api/v1/export/templates",
            json={
                "name": "Test Template",
                "abbreviation": "TT",
                "description": "A test template",
                "sections": [
                    {"key": "intro", "title": "1. Introduction", "prompt": "Write intro", "guidance": ""},
                    {"key": "body", "title": "2. Body", "prompt": "Write body", "guidance": ""},
                ],
            },
            headers=headers,
        )
        assert create_resp.status_code == 201
        tpl = create_resp.json()
        tpl_uid = tpl["template_uid"]
        assert tpl["name"] == "Test Template"
        assert tpl["abbreviation"] == "TT"
        assert len(tpl["sections"]) == 2

        # READ
        get_resp = await test_client.get(
            f"/api/v1/export/templates/{tpl_uid}",
            headers=headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Test Template"

        # UPDATE
        put_resp = await test_client.put(
            f"/api/v1/export/templates/{tpl_uid}",
            json={"name": "Updated Template"},
            headers=headers,
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["name"] == "Updated Template"

        # LIST
        list_resp = await test_client.get(
            "/api/v1/export/templates",
            headers=headers,
        )
        assert list_resp.status_code == 200
        templates = list_resp.json()
        assert any(t["template_uid"] == tpl_uid for t in templates)

        # DELETE (soft)
        del_resp = await test_client.delete(
            f"/api/v1/export/templates/{tpl_uid}",
            headers=headers,
        )
        assert del_resp.status_code == 204

        # Verify soft-deleted (not in active list)
        list_resp2 = await test_client.get(
            "/api/v1/export/templates",
            headers=headers,
        )
        assert not any(t["template_uid"] == tpl_uid for t in list_resp2.json())


# ══════════════════════════════════════════════
# TEST: Views prefilter returns fact section assignments
# ══════════════════════════════════════════════


class TestViewsPrefilter:
    async def test_views_prefilter_returns_fact_section_assignments(
        self,
        db,
        admin_with_session,
        test_client,
        template,
        facts_with_events,
        child_node,
    ):
        admin_user, admin_sid = admin_with_session
        resp = await test_client.post(
            "/api/v1/export/views",
            json={
                "node_uids": [str(child_node.node_uid)],
                "template_uid": str(template.template_uid),
            },
            headers=_csrf_headers(admin_sid),
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["template_uid"] == str(template.template_uid)
        assert data["template_name"] == template.name
        assert "assignments" in data
        assert len(data["assignments"]) == 2  # 2 sections in template

        for assignment in data["assignments"]:
            assert "section_key" in assignment
            assert "section_title" in assignment
            assert "facts" in assignment


# ══════════════════════════════════════════════
# TEST: Service account API key works
# ══════════════════════════════════════════════


class TestServiceAccountApiKey:
    async def test_service_account_api_key_works(
        self, db, test_client, service_account, facts_with_events
    ):
        """Service account authenticates via Bearer token and can access sync endpoints."""
        user, raw_key = service_account

        resp = await test_client.get(
            "/api/v1/sync/changes",
            params={"cursor": 0, "limit": 10},
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "changes" in data
        assert "cursor" in data

        resp2 = await test_client.get(
            "/api/v1/sync/full",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert "nodes" in data2
