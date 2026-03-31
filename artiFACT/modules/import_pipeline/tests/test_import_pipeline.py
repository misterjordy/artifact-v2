"""Import pipeline v2 tests — staged facts, classifier, conflict detector, paste."""

import json
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, generate_csrf_token
from artiFACT.kernel.auth.session import create_session, get_redis, update_session_field
from artiFACT.kernel.models import (
    FcImportSession,
    FcImportStagedFact,
    FcNode,
    FcUser,
)
from artiFACT.main import app
from artiFACT.modules.import_pipeline.deduplicator import deduplicate, jaccard, tokenize


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
async def no_perm_client(db: AsyncSession):
    """HTTP client with a user that has NO permissions on the root node."""
    from artiFACT.kernel.db import get_db

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db

    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=No Perms {uuid.uuid4().hex[:8]}",
        display_name="No Perms User",
        global_role="viewer",
    )
    db.add(user)
    await db.flush()

    session_id = await create_session(user)
    csrf_token = generate_csrf_token()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.cookies.set("session_id", session_id)
        client.cookies.set(CSRF_COOKIE_NAME, csrf_token)
        client.headers[CSRF_HEADER_NAME] = csrf_token
        yield client

    app.dependency_overrides.clear()


# === Session + paste ===


@pytest.mark.asyncio
async def test_paste_creates_session_with_text_type(
    authed_client: AsyncClient,
    db: AsyncSession,
    root_node: FcNode,
):
    """POST /api/v1/import/paste creates session with input_type='text'."""
    with patch(
        "artiFACT.modules.import_pipeline.analyzer.analyze_document.delay"
    ) as mock_delay:
        resp = await authed_client.post(
            "/api/v1/import/paste",
            json={
                "text": "The system has 22 transverse bulkheads and operates at full capacity.",
                "program_node_uid": str(root_node.node_uid),
                "effective_date": "2026-01-15",
                "granularity": "standard",
            },
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "analyzing"
    session_uid = data["session_uid"]

    session = await db.get(FcImportSession, session_uid)
    assert session is not None
    assert session.input_type == "text"
    assert session.source_text is not None
    assert "transverse bulkheads" in session.source_text
    mock_delay.assert_called_once()


@pytest.mark.asyncio
async def test_paste_requires_contribute_permission(
    no_perm_client: AsyncClient,
    root_node: FcNode,
):
    """POST /paste without contribute permission returns 403."""
    resp = await no_perm_client.post(
        "/api/v1/import/paste",
        json={
            "text": "The system operates at full power with 50MW capacity.",
            "program_node_uid": str(root_node.node_uid),
            "effective_date": "2026-01-15",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_auto_approve_forced_off_on_import_start(
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """auto_approve is forced False when import starts."""
    from artiFACT.kernel.db import get_db

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db

    session_id = await create_session(import_contributor)
    csrf_token = generate_csrf_token()

    # Set auto_approve to True
    await update_session_field(session_id, "auto_approve", True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.cookies.set("session_id", session_id)
        client.cookies.set(CSRF_COOKIE_NAME, csrf_token)
        client.headers[CSRF_HEADER_NAME] = csrf_token

        with patch(
            "artiFACT.modules.import_pipeline.analyzer.analyze_document.delay"
        ):
            resp = await client.post(
                "/api/v1/import/paste",
                json={
                    "text": "The system operates at maximum capacity of 100MW output.",
                    "program_node_uid": str(root_node.node_uid),
                    "effective_date": "2026-01-15",
                },
            )

    assert resp.status_code == 201

    # Verify auto_approve was forced off
    r = await get_redis()
    raw = await r.get(f"session:{session_id}")
    session_data = json.loads(raw)
    assert session_data["auto_approve"] is False

    app.dependency_overrides.clear()


# === Staging persistence ===


@pytest.mark.asyncio
async def test_staged_facts_persisted_in_postgres(
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """Staged facts are stored in fc_import_staged_fact."""
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

    sf = FcImportStagedFact(
        staged_fact_uid=uuid.uuid4(),
        session_uid=session.session_uid,
        display_sentence="The system has 22 transverse bulkheads.",
        status="pending",
        node_alternatives=[],
        metadata_tags=["structure"],
    )
    db.add(sf)
    await db.flush()

    result = await db.execute(
        select(FcImportStagedFact).where(
            FcImportStagedFact.session_uid == session.session_uid
        )
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].display_sentence == "The system has 22 transverse bulkheads."


@pytest.mark.asyncio
async def test_staged_facts_survive_session_close(
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """Staged facts persist in Postgres across queries (no browser dependency)."""
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

    sf = FcImportStagedFact(
        staged_fact_uid=uuid.uuid4(),
        session_uid=session.session_uid,
        display_sentence="The hull has 112 watertight compartments.",
        status="pending",
        node_alternatives=[],
        metadata_tags=[],
    )
    db.add(sf)
    await db.flush()

    # Query again as if in a new request
    result = await db.execute(
        select(FcImportStagedFact).where(
            FcImportStagedFact.session_uid == session.session_uid
        )
    )
    facts = result.scalars().all()
    assert len(facts) == 1
    assert facts[0].display_sentence == "The hull has 112 watertight compartments."


@pytest.mark.asyncio
async def test_reset_deletes_staged_facts(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """POST /reset deletes all staged facts for the session."""
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

    for i in range(3):
        sf = FcImportStagedFact(
            staged_fact_uid=uuid.uuid4(),
            session_uid=session.session_uid,
            display_sentence=f"Fact number {i} for reset test.",
            status="pending",
            node_alternatives=[],
            metadata_tags=[],
        )
        db.add(sf)
    await db.flush()

    with patch("artiFACT.kernel.s3.get_s3_client"):
        resp = await authed_client.post(
            f"/api/v1/import/sessions/{session.session_uid}/reset",
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "reset"

    result = await db.execute(
        select(FcImportStagedFact).where(
            FcImportStagedFact.session_uid == session.session_uid
        )
    )
    assert len(result.scalars().all()) == 0

    await db.refresh(session)
    assert session.status == "discarded"


# === Classifier ===


@pytest.mark.asyncio
async def test_classifier_batches_8_facts():
    """classify_all sends ceil(20/8) = 3 AI calls."""
    from artiFACT.modules.import_pipeline.classifier import classify_all

    facts = [f"Fact number {i}" for i in range(20)]
    taxonomy_text = "1 Root\n2 Child A\n3 Child B"
    id_mapping = {1: str(uuid.uuid4()), 2: str(uuid.uuid4()), 3: str(uuid.uuid4())}

    call_count = 0

    def _make_response(batch_facts: list[str]) -> dict:
        nonlocal call_count
        call_count += 1
        results = []
        for i in range(len(batch_facts)):
            results.append({
                "fact": i + 1,
                "nodes": [
                    {"id": 1, "confidence": 0.9, "reason": "top match"},
                    {"id": 2, "confidence": 0.7, "reason": "alt 1"},
                    {"id": 3, "confidence": 0.5, "reason": "alt 2"},
                ],
            })
        return {"results": results}

    async def _mock_post(self, url, **kwargs):
        msgs = kwargs.get("json", {}).get("messages", [])
        user_msg = msgs[-1]["content"] if msgs else ""
        # Count facts in user message
        fact_lines = [l for l in user_msg.split("\n") if l.strip().startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8."))]
        batch_size = max(len(fact_lines), 1)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(_make_response(facts[:batch_size]))}}]
        }
        return mock_resp

    with patch("httpx.AsyncClient.post", new=_mock_post):
        results = await classify_all(facts, taxonomy_text, id_mapping, "fake-key")

    assert call_count == 3  # 8 + 8 + 4
    assert len(results) == 20


@pytest.mark.asyncio
async def test_classifier_uses_integer_ids_not_uuids(
    db: AsyncSession,
    root_node: FcNode,
):
    """build_taxonomy_index returns integer IDs, not UUIDs."""
    from artiFACT.modules.import_pipeline.classifier import build_taxonomy_index

    taxonomy_text, id_mapping = await build_taxonomy_index(db, root_node.node_uid)

    # Taxonomy text should have integer IDs
    assert "1 " in taxonomy_text or "1  " in taxonomy_text
    # Should NOT contain UUID strings (36 chars with hyphens)
    import re
    uuid_pattern = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    assert not uuid_pattern.search(taxonomy_text)
    # id_mapping maps ints to UUID strings
    for k, v in id_mapping.items():
        assert isinstance(k, int)
        assert uuid_pattern.match(v)


@pytest.mark.asyncio
async def test_classifier_top1_becomes_suggested_node():
    """Top-1 node from classifier becomes suggested_node_uid."""
    from artiFACT.modules.import_pipeline.classifier import classify_batch

    node_uid_1 = str(uuid.uuid4())
    node_uid_2 = str(uuid.uuid4())
    node_uid_3 = str(uuid.uuid4())
    id_mapping = {1: node_uid_1, 2: node_uid_2, 3: node_uid_3}

    mock_response = {
        "results": [{
            "fact": 1,
            "nodes": [
                {"id": 1, "confidence": 0.92, "reason": "best match"},
                {"id": 2, "confidence": 0.78, "reason": "second"},
                {"id": 3, "confidence": 0.65, "reason": "third"},
            ],
        }]
    }

    async def _mock_post(self, url, **kwargs):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(mock_response)}}]
        }
        return mock_resp

    with patch("httpx.AsyncClient.post", new=_mock_post):
        results = await classify_batch(
            ["Test fact one."], "1 Root\n2 Child\n3 Leaf", id_mapping, "fake-key"
        )

    assert len(results) == 1
    assert results[0]["suggested_node_uid"] == node_uid_1
    assert results[0]["node_confidence"] == 0.92


@pytest.mark.asyncio
async def test_classifier_ranks_2_3_in_alternatives():
    """Ranks 2-3 from classifier go into node_alternatives."""
    from artiFACT.modules.import_pipeline.classifier import classify_batch

    uids = {i: str(uuid.uuid4()) for i in range(1, 4)}

    mock_response = {
        "results": [{
            "fact": 1,
            "nodes": [
                {"id": 1, "confidence": 0.92, "reason": "top"},
                {"id": 2, "confidence": 0.78, "reason": "second best"},
                {"id": 3, "confidence": 0.65, "reason": "third option"},
            ],
        }]
    }

    async def _mock_post(self, url, **kwargs):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(mock_response)}}]
        }
        return mock_resp

    with patch("httpx.AsyncClient.post", new=_mock_post):
        results = await classify_batch(
            ["Test fact."], "1 A\n2 B\n3 C", uids, "fake-key"
        )

    alts = results[0]["node_alternatives"]
    assert len(alts) == 2
    assert alts[0]["node_uid"] == uids[2]
    assert alts[0]["confidence"] == 0.78
    assert alts[0]["reason"] == "second best"
    assert alts[1]["node_uid"] == uids[3]


@pytest.mark.asyncio
async def test_node_constraint_appears_in_classifier_prompt():
    """constraint_node_uids adds a 'Priority nodes' hint to the prompt."""
    from artiFACT.modules.import_pipeline.classifier import classify_batch

    uid_1 = str(uuid.uuid4())
    uid_2 = str(uuid.uuid4())
    id_mapping = {1: uid_1, 2: uid_2}

    captured_messages: list[dict] = []

    async def _mock_post(self, url, **kwargs):
        captured_messages.append(kwargs.get("json", {}))
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({"results": [{"fact": 1, "nodes": [{"id": 1, "confidence": 0.9, "reason": "match"}]}]})}}]
        }
        return mock_resp

    with patch("httpx.AsyncClient.post", new=_mock_post):
        await classify_batch(
            ["Test fact."], "1 Node A\n2 Node B", id_mapping, "fake-key",
            constraint_node_uids=[uid_1],
        )

    user_msg = captured_messages[0]["messages"][-1]["content"]
    assert "Priority nodes" in user_msg


# === Duplicate detection ===


@pytest.mark.asyncio
async def test_duplicate_above_085_flagged_mechanically():
    """Jaccard > 0.85 is flagged as duplicate without any AI call."""
    existing = [
        {"sentence": "The system operates at 99.9% uptime availability.", "fact_uid": "existing-1"},
    ]
    new_facts = [
        {"sentence": "The system operates at 99.9% uptime availability."},
    ]

    results = deduplicate(new_facts, existing, threshold=0.85)
    assert results[0].get("duplicate_of") == "existing-1"
    assert results[0]["similarity"] >= 0.85


# === Conflict detection ===


@pytest.mark.asyncio
async def test_conflict_only_jaccard_03_to_085():
    """Conflict detector only checks facts in Jaccard 0.3-0.85 range."""
    from artiFACT.modules.import_pipeline.conflict_detector import detect_conflicts

    staged_uid = uuid.uuid4()
    staged = FcImportStagedFact(
        staged_fact_uid=staged_uid,
        session_uid=uuid.uuid4(),
        display_sentence="The system operates at 50MW capacity.",
        status="pending",
        node_alternatives=[],
        metadata_tags=[],
    )

    # Existing facts at various similarity levels
    existing: list[tuple[str, uuid.UUID]] = [
        # Jaccard ~0.2 (too different, should skip)
        ("The submarine has 6 torpedo tubes and nuclear propulsion.", uuid.uuid4()),
        # Jaccard ~0.5 (in range, should check)
        ("The system operates at 75MW capacity during peak hours.", uuid.uuid4()),
        # Jaccard ~0.95 (too similar = duplicate, should skip)
        ("The system operates at 50MW capacity.", uuid.uuid4()),
    ]

    ai_call_count = 0

    async def _mock_post(self, url, **kwargs):
        nonlocal ai_call_count
        ai_call_count += 1
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps({"results": []})}}]
        }
        return mock_resp

    with patch("httpx.AsyncClient.post", new=_mock_post):
        results = await detect_conflicts(
            [staged], existing, "fake-key", jaccard, tokenize
        )

    # Only one AI call — for the fact in the 0.3-0.85 range
    assert ai_call_count == 1


@pytest.mark.asyncio
async def test_conflict_detected_sets_fields():
    """When AI detects a contradiction, conflict fields are set."""
    from artiFACT.modules.import_pipeline.conflict_detector import detect_conflicts

    staged_uid = uuid.uuid4()
    existing_version_uid = uuid.uuid4()

    staged = FcImportStagedFact(
        staged_fact_uid=staged_uid,
        session_uid=uuid.uuid4(),
        display_sentence="The system operates at 50MW capacity.",
        status="pending",
        node_alternatives=[],
        metadata_tags=[],
    )

    existing: list[tuple[str, uuid.UUID]] = [
        ("The system operates at 75MW capacity during peak load.", existing_version_uid),
    ]

    mock_ai_response = {
        "results": [{"existing": 1, "contradicts": True, "reason": "Incompatible MW values"}]
    }

    async def _mock_post(self, url, **kwargs):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(mock_ai_response)}}]
        }
        return mock_resp

    with patch("httpx.AsyncClient.post", new=_mock_post):
        results = await detect_conflicts(
            [staged], existing, "fake-key", jaccard, tokenize
        )

    assert len(results) == 1
    assert results[0]["staged_fact_uid"] == staged_uid
    assert results[0]["conflict_with_uid"] == existing_version_uid
    assert "MW" in results[0]["conflict_reason"]


# === Granularity ===


@pytest.mark.asyncio
async def test_granularity_controls_max_facts_per_chunk():
    """Granularity 'brief' should use max_facts=10 in extractor prompt."""
    from artiFACT.modules.import_pipeline.prompts import GRANULARITY_MAP

    assert GRANULARITY_MAP["brief"] == 10
    assert GRANULARITY_MAP["standard"] == 25
    assert GRANULARITY_MAP["exhaustive"] == 50


# === Rerun ===


@pytest.mark.asyncio
async def test_rerun_reclassifies_without_reextracting(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """POST /rerun triggers reanalysis, classifier called, extractor NOT called."""
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

    # Add staged facts
    for i in range(3):
        sf = FcImportStagedFact(
            staged_fact_uid=uuid.uuid4(),
            session_uid=session.session_uid,
            display_sentence=f"Rerun test fact {i}.",
            status="pending",
            source_chunk_index=i,
            node_alternatives=[],
            metadata_tags=[],
        )
        db.add(sf)
    await db.flush()

    with patch(
        "artiFACT.modules.import_pipeline.analyzer.rerun_analysis.delay"
    ) as mock_delay:
        resp = await authed_client.post(
            f"/api/v1/import/sessions/{session.session_uid}/rerun",
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "analyzing"
    mock_delay.assert_called_once_with(str(session.session_uid))


# === Staged facts API ===


@pytest.mark.asyncio
async def test_get_staged_facts_from_postgres(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """GET /staged returns facts from Postgres, not S3."""
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

    sf = FcImportStagedFact(
        staged_fact_uid=uuid.uuid4(),
        session_uid=session.session_uid,
        display_sentence="API test fact from Postgres.",
        suggested_node_uid=root_node.node_uid,
        node_confidence=0.88,
        status="pending",
        source_chunk_index=0,
        node_alternatives=[{"node_uid": str(uuid.uuid4()), "confidence": 0.7, "reason": "alt"}],
        metadata_tags=["test"],
    )
    db.add(sf)
    await db.flush()

    resp = await authed_client.get(
        f"/api/v1/import/sessions/{session.session_uid}/staged",
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    fact = data["facts"][0]
    assert fact["display_sentence"] == "API test fact from Postgres."
    assert fact["node_confidence"] == 0.88
    assert fact["status"] == "pending"


@pytest.mark.asyncio
async def test_patch_staged_fact(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """PATCH /staged/{uid} updates individual fact fields."""
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

    sf_uid = uuid.uuid4()
    sf = FcImportStagedFact(
        staged_fact_uid=sf_uid,
        session_uid=session.session_uid,
        display_sentence="Original sentence.",
        status="pending",
        source_chunk_index=0,
        node_alternatives=[],
        metadata_tags=[],
    )
    db.add(sf)
    await db.flush()

    resp = await authed_client.patch(
        f"/api/v1/import/staged/{sf_uid}",
        json={"display_sentence": "Edited sentence.", "status": "accepted"},
    )

    assert resp.status_code == 200

    await db.refresh(sf)
    assert sf.display_sentence == "Edited sentence."
    assert sf.original_sentence == "Original sentence."
    assert sf.status == "accepted"


# === Import page renders ===


@pytest.mark.asyncio
async def test_import_page_renders_with_tabs(
    authed_client: AsyncClient,
):
    """GET /import returns 200 with paste and upload tabs."""
    resp = await authed_client.get("/import")
    assert resp.status_code == 200
    body = resp.text
    assert "Paste Text" in body
    assert "Upload Document" in body


# === Staging review grouped facts ===


@pytest.mark.asyncio
async def test_staging_review_returns_grouped_by_node(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """GET /staged returns facts with node_title for grouping."""
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

    sf = FcImportStagedFact(
        staged_fact_uid=uuid.uuid4(),
        session_uid=session.session_uid,
        display_sentence="Grouped test fact.",
        suggested_node_uid=root_node.node_uid,
        node_confidence=0.91,
        status="pending",
        source_chunk_index=0,
        node_alternatives=[],
        metadata_tags=[],
    )
    db.add(sf)
    await db.flush()

    resp = await authed_client.get(
        f"/api/v1/import/sessions/{session.session_uid}/staged",
    )
    assert resp.status_code == 200
    data = resp.json()
    fact = data["facts"][0]
    # node_title should be resolved from the node UID
    assert fact["node_title"] == root_node.title


# === Resolution PATCH ===


@pytest.mark.asyncio
async def test_resolution_patch_updates_staged_fact(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """PATCH with resolution updates status and resolution fields."""
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

    sf_uid = uuid.uuid4()
    sf = FcImportStagedFact(
        staged_fact_uid=sf_uid,
        session_uid=session.session_uid,
        display_sentence="Duplicate resolution test.",
        status="duplicate",
        source_chunk_index=0,
        node_alternatives=[],
        metadata_tags=[],
    )
    db.add(sf)
    await db.flush()

    resp = await authed_client.patch(
        f"/api/v1/import/staged/{sf_uid}",
        json={"resolution": "keep_new", "status": "accepted"},
    )
    assert resp.status_code == 200

    await db.refresh(sf)
    assert sf.resolution == "keep_new"
    assert sf.status == "accepted"
    assert sf.resolved_at is not None


# === Download unresolved ===


@pytest.mark.asyncio
async def test_download_unresolved_returns_txt(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """GET /download-unresolved returns text/plain with unresolved facts."""
    session = FcImportSession(
        session_uid=uuid.uuid4(),
        program_node_uid=root_node.node_uid,
        source_filename="report.txt",
        source_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        effective_date=date(2026, 1, 15),
        status="staged",
        created_by_uid=import_contributor.user_uid,
    )
    db.add(session)
    await db.flush()

    # Add facts with different statuses
    for status_val, sentence in [
        ("duplicate", "Dup fact for download."),
        ("conflict", "Conflict fact for download."),
        ("orphaned", "Orphaned fact for download."),
        ("pending", "Pending fact should NOT be in download."),
    ]:
        sf = FcImportStagedFact(
            staged_fact_uid=uuid.uuid4(),
            session_uid=session.session_uid,
            display_sentence=sentence,
            status=status_val,
            source_chunk_index=0,
            node_alternatives=[],
            metadata_tags=[],
        )
        db.add(sf)
    await db.flush()

    resp = await authed_client.get(
        f"/api/v1/import/sessions/{session.session_uid}/download-unresolved",
    )
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    assert "Dup fact for download" in body
    assert "Conflict fact for download" in body
    assert "Orphaned fact for download" in body
    assert "Pending fact should NOT" not in body


# === Staged facts include existing sentence ===


@pytest.mark.asyncio
async def test_staged_facts_include_existing_sentence_for_duplicates(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """GET /staged returns existing_sentence when duplicate_of_uid is set."""
    from artiFACT.kernel.models import FcFact, FcFactVersion

    # Create an existing fact with a version
    fact = FcFact(
        node_uid=root_node.node_uid,
        created_by_uid=import_contributor.user_uid,
    )
    db.add(fact)
    await db.flush()

    version = FcFactVersion(
        fact_uid=fact.fact_uid,
        state="published",
        display_sentence="The existing system runs at 99.9% uptime.",
        effective_date="2026-01-01",
        created_by_uid=import_contributor.user_uid,
    )
    db.add(version)
    await db.flush()

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

    sf = FcImportStagedFact(
        staged_fact_uid=uuid.uuid4(),
        session_uid=session.session_uid,
        display_sentence="The system runs at 99.9% uptime.",
        status="duplicate",
        duplicate_of_uid=version.version_uid,
        similarity_score=0.92,
        source_chunk_index=0,
        node_alternatives=[],
        metadata_tags=[],
    )
    db.add(sf)
    await db.flush()

    resp = await authed_client.get(
        f"/api/v1/import/sessions/{session.session_uid}/staged",
    )
    assert resp.status_code == 200
    data = resp.json()
    fact_data = data["facts"][0]
    assert fact_data["existing_sentence"] == "The existing system runs at 99.9% uptime."
