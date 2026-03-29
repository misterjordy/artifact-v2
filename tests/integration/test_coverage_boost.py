"""Additional tests to ensure >= 80% coverage across artiFACT modules."""

from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import (
    FcFact,
    FcNode,
    FcUser,
)


async def test_fact_service_create(db: AsyncSession, admin_user: FcUser, root_node: FcNode) -> None:
    """Test fact creation at service layer."""
    from artiFACT.modules.facts.service import create_fact

    fact, version = await create_fact(
        db=db,
        node_uid=root_node.node_uid,
        sentence="Test fact for coverage.",
        actor=admin_user,
    )
    assert fact.fact_uid is not None
    assert version.version_uid is not None
    assert version.display_sentence == "Test fact for coverage."


async def test_fact_service_list_by_node(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode
) -> None:
    """Test fact listing by node."""
    from artiFACT.modules.facts.service import create_fact, get_facts_by_node

    await create_fact(
        db=db,
        node_uid=root_node.node_uid,
        sentence="List test fact.",
        actor=admin_user,
    )
    facts = await get_facts_by_node(db, root_node.node_uid)
    assert len(facts) >= 1


async def test_export_sync_delta(db: AsyncSession, admin_user: FcUser) -> None:
    """Test delta feed retrieval."""
    from artiFACT.modules.export.sync import get_delta_feed

    result = await get_delta_feed(db, cursor=0, limit=10)
    assert "changes" in result
    assert "cursor" in result
    assert "has_more" in result


async def test_export_sync_full(db: AsyncSession) -> None:
    """Test full dump retrieval."""
    from artiFACT.modules.export.sync import get_full_dump

    result = await get_full_dump(db)
    assert "exported_at" in result
    assert "schema_version" in result
    assert "nodes" in result
    assert "facts" in result


async def test_audit_service_get_events(db: AsyncSession, admin_user: FcUser) -> None:
    """Test audit event retrieval."""
    from artiFACT.modules.audit.service import get_all_events

    result = await get_all_events(db)
    # Returns (events_list, total_count) or similar tuple
    if isinstance(result, tuple):
        events = result[0]
    else:
        events = result
    assert isinstance(events, list)


async def test_batch_signer(db: AsyncSession, admin_user: FcUser, root_node: FcNode) -> None:
    """Test batch signing."""
    from artiFACT.modules.facts.service import create_fact
    from artiFACT.modules.signing.service import sign_node

    await create_fact(
        db=db,
        node_uid=root_node.node_uid,
        sentence="Fact to sign.",
        actor=admin_user,
    )

    sig = await sign_node(db, root_node.node_uid, admin_user)
    assert sig.signature_uid is not None


async def test_fact_version_state_transitions() -> None:
    """Test fact version state transitions."""
    from artiFACT.modules.facts.state_machine import ALLOWED_TRANSITIONS

    assert "published" in ALLOWED_TRANSITIONS["proposed"]
    assert "rejected" in ALLOWED_TRANSITIONS["proposed"]
    assert "proposed" not in ALLOWED_TRANSITIONS.get("published", [])
    assert "signed" in ALLOWED_TRANSITIONS["published"]


async def test_export_factsheet_load(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode
) -> None:
    """Test factsheet data loading."""
    from artiFACT.modules.facts.service import create_fact
    from artiFACT.modules.export.factsheet import load_facts_for_export

    await create_fact(
        db=db,
        node_uid=root_node.node_uid,
        sentence="Export this fact.",
        actor=admin_user,
    )

    facts = await load_facts_for_export(db, [root_node.node_uid], ["published"])
    assert isinstance(facts, list)


async def test_queue_scope_resolver(db: AsyncSession, approver_user: FcUser) -> None:
    """Test scope resolver for queue."""
    from artiFACT.modules.queue.scope_resolver import get_approvable_nodes

    result = await get_approvable_nodes(db, approver_user)
    assert isinstance(result, dict)


async def test_dashboard_stats(db: AsyncSession) -> None:
    """Test admin dashboard stats computation."""
    from artiFACT.modules.admin.dashboard import get_dashboard

    stats = await get_dashboard(db)
    assert isinstance(stats, dict)


async def test_fact_retire_unretire(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode
) -> None:
    """Test fact retire and unretire."""
    from artiFACT.modules.facts.service import create_fact, retire_fact, unretire_fact

    fact, _ = await create_fact(
        db=db,
        node_uid=root_node.node_uid,
        sentence="Retiring this fact.",
        actor=admin_user,
    )

    await retire_fact(db, fact.fact_uid, admin_user)
    refreshed = await db.get(FcFact, fact.fact_uid)
    assert refreshed is not None
    assert refreshed.is_retired is True

    await unretire_fact(db, fact.fact_uid, admin_user)
    refreshed2 = await db.get(FcFact, fact.fact_uid)
    assert refreshed2 is not None
    assert refreshed2.is_retired is False


async def test_fact_edit(db: AsyncSession, admin_user: FcUser, root_node: FcNode) -> None:
    """Test fact editing creates a new version."""
    from artiFACT.modules.facts.service import create_fact, edit_fact

    fact, version = await create_fact(
        db=db,
        node_uid=root_node.node_uid,
        sentence="Original sentence.",
        actor=admin_user,
    )

    result = await edit_fact(
        db=db,
        fact_uid=fact.fact_uid,
        sentence="Updated sentence.",
        actor=admin_user,
        change_summary="Fixed wording.",
    )
    # edit_fact may return (fact, version) tuple or just version
    new_version = result[1] if isinstance(result, tuple) else result
    assert new_version.display_sentence == "Updated sentence."
    assert new_version.version_uid != version.version_uid


async def test_fact_get_versions(db: AsyncSession, admin_user: FcUser, root_node: FcNode) -> None:
    """Test getting all versions of a fact."""
    from artiFACT.modules.facts.service import create_fact, get_fact_versions

    fact, _ = await create_fact(
        db=db,
        node_uid=root_node.node_uid,
        sentence="Versioned fact.",
        actor=admin_user,
    )

    versions = await get_fact_versions(db, fact.fact_uid)
    assert len(versions) >= 1
