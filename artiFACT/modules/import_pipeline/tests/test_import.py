"""Import pipeline integration tests — real CSRF, real rate limiter, real transactions."""

import io
import json
import uuid
from datetime import date
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, generate_csrf_token
from artiFACT.kernel.auth.session import create_session
from artiFACT.kernel.models import (
    FcImportSession,
    FcNode,
    FcUser,
)
from artiFACT.main import app
from artiFACT.modules.import_pipeline.deduplicator import deduplicate


@pytest_asyncio.fixture
async def authed_client(db: AsyncSession, import_contributor: FcUser):
    """HTTP client with valid session cookie and CSRF token."""
    from artiFACT.kernel.db import get_db

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db

    session_id = await create_session(import_contributor)
    csrf_token = generate_csrf_token()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.cookies.set("session_id", session_id)
        client.cookies.set(CSRF_COOKIE_NAME, csrf_token)
        client.headers[CSRF_HEADER_NAME] = csrf_token
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def no_csrf_client(db: AsyncSession, import_contributor: FcUser):
    """HTTP client with valid session but NO CSRF token."""
    from artiFACT.kernel.db import get_db

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db

    session_id = await create_session(import_contributor)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.cookies.set("session_id", session_id)
        yield client

    app.dependency_overrides.clear()


def _make_txt_upload(
    content: str = "The system operates at 99.9% uptime.", filename: str = "test.txt"
):
    """Create a simple text file upload."""
    return ("file", (filename, io.BytesIO(content.encode()), "text/plain"))


# --- v1 I-SEC-01: CSRF required on propose ---


@pytest.mark.asyncio
async def test_csrf_required_on_propose(
    no_csrf_client: AsyncClient,
    root_node: FcNode,
):
    """POST /propose without CSRF token must return 403."""
    fake_uid = str(uuid.uuid4())
    resp = await no_csrf_client.post(
        f"/api/v1/import/sessions/{fake_uid}/propose",
        json={"accepted_indices": [0]},
    )
    assert resp.status_code == 403
    assert "CSRF" in resp.json()["detail"]


# --- v1 I-SEC-02: CSRF required on upload ---


@pytest.mark.asyncio
async def test_csrf_required_on_upload(
    no_csrf_client: AsyncClient,
    root_node: FcNode,
):
    """POST /upload without CSRF token must return 403."""
    resp = await no_csrf_client.post(
        "/api/v1/import/upload",
        data={
            "program_node_uid": str(root_node.node_uid),
            "effective_date": "2026-01-15",
        },
        files=[_make_txt_upload()],
    )
    assert resp.status_code == 403
    assert "CSRF" in resp.json()["detail"]


# --- v1 I-SEC-03: Rate limited on analyze ---


@pytest.mark.asyncio
async def test_rate_limited_on_analyze(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """POST /analyze must enforce rate limiting."""
    from artiFACT.kernel.auth.session import get_redis

    r = await get_redis()

    # Set the rate counter just below threshold, then exceed
    rate_key = f"rate:api_write:{import_contributor.user_uid}"
    await r.set(rate_key, "50")
    await r.expire(rate_key, 3600)

    fake_session = FcImportSession(
        session_uid=uuid.uuid4(),
        program_node_uid=root_node.node_uid,
        source_filename="test.txt",
        source_hash="a" * 64,
        effective_date=date(2026, 1, 15),
        created_by_uid=import_contributor.user_uid,
    )
    db.add(fake_session)
    await db.flush()

    resp = await authed_client.post(
        f"/api/v1/import/analyze/{fake_session.session_uid}",
    )
    assert resp.status_code == 429

    # cleanup
    await r.delete(rate_key)


# --- test_analysis_runs_as_background_task_not_blocking ---


@pytest.mark.asyncio
async def test_analysis_runs_as_background_task_not_blocking(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """POST /analyze dispatches Celery task and returns immediately."""
    session = FcImportSession(
        session_uid=uuid.uuid4(),
        program_node_uid=root_node.node_uid,
        source_filename="test.txt",
        source_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        effective_date=date(2026, 1, 15),
        created_by_uid=import_contributor.user_uid,
    )
    db.add(session)
    await db.flush()

    # Mock only the Celery .delay() call (external task dispatch)
    with patch("artiFACT.modules.import_pipeline.analyzer.analyze_document.delay") as mock_delay:
        resp = await authed_client.post(
            f"/api/v1/import/analyze/{session.session_uid}",
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "analyzing"
    mock_delay.assert_called_once_with(str(session.session_uid))


# --- test_propose_all_or_nothing_transaction ---


@pytest.mark.asyncio
async def test_propose_all_or_nothing_transaction(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """Propose creates facts in an all-or-nothing transaction."""
    from artiFACT.kernel.models import FcImportStagedFact

    session = FcImportSession(
        session_uid=uuid.uuid4(),
        program_node_uid=root_node.node_uid,
        source_filename="test.txt",
        source_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        effective_date=date(2026, 1, 15),
        status="staged",
        created_by_uid=import_contributor.user_uid,
    )
    db.add(session)
    await db.flush()

    # Create staged facts in Postgres (new flow)
    for i, sentence in enumerate([
        "Fact alpha from import test one two three.",
        "Fact beta from import test four five six.",
    ]):
        sf = FcImportStagedFact(
            staged_fact_uid=uuid.uuid4(),
            session_uid=session.session_uid,
            display_sentence=sentence,
            suggested_node_uid=root_node.node_uid,
            status="pending",
            source_chunk_index=i,
            node_alternatives=[],
            metadata_tags=["test"] if i == 0 else [],
        )
        db.add(sf)
    await db.flush()

    resp = await authed_client.post(
        f"/api/v1/import/sessions/{session.session_uid}/propose",
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["created"] == 2

    # Verify session status updated
    await db.refresh(session)
    assert session.status == "proposed"


# --- test_duplicate_detection_flags_similar ---


@pytest.mark.asyncio
async def test_duplicate_detection_flags_similar():
    """Jaccard deduplicator flags facts above threshold."""
    existing = [
        {"sentence": "The system operates at 99.9% uptime availability.", "fact_uid": "existing-1"},
    ]
    new_facts = [
        {"sentence": "The system operates at 99.9% uptime availability."},
        {"sentence": "The network latency is below 50 milliseconds."},
    ]

    results = deduplicate(new_facts, existing, threshold=0.85)

    # First fact is a near-exact duplicate
    assert results[0].get("duplicate_of") == "existing-1"
    assert results[0]["similarity"] >= 0.85

    # Second fact is unique
    assert results[1].get("duplicate_of") is None


# --- test_file_size_limit_enforced ---


@pytest.mark.asyncio
async def test_file_size_limit_enforced(
    authed_client: AsyncClient,
    root_node: FcNode,
):
    """Upload rejects files exceeding MAX_FILE_SIZE."""
    # Create content that exceeds 50MB limit
    from artiFACT.modules.import_pipeline.upload_handler import MAX_FILE_SIZE

    # Mock S3 to avoid actual upload, create oversized content
    oversized = b"x" * (MAX_FILE_SIZE + 1)

    with patch("artiFACT.kernel.s3.upload_bytes"):
        resp = await authed_client.post(
            "/api/v1/import/upload",
            data={
                "program_node_uid": str(root_node.node_uid),
                "effective_date": "2026-01-15",
            },
            files=[("file", ("big.txt", io.BytesIO(oversized), "text/plain"))],
        )

    assert resp.status_code == 422
    assert "too large" in resp.json()["detail"].lower()


# --- test_unsupported_file_type_rejected ---


@pytest.mark.asyncio
async def test_unsupported_file_type_rejected(
    authed_client: AsyncClient,
    root_node: FcNode,
):
    """Upload rejects unsupported file types."""
    resp = await authed_client.post(
        "/api/v1/import/upload",
        data={
            "program_node_uid": str(root_node.node_uid),
            "effective_date": "2026-01-15",
        },
        files=[("file", ("malware.exe", io.BytesIO(b"bad content"), "application/octet-stream"))],
    )

    assert resp.status_code == 422
    assert "unsupported" in resp.json()["detail"].lower()
