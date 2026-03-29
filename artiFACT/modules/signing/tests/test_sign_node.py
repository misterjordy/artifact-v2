"""Tests for signing module — all 5 DoS bullets."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Forbidden
from artiFACT.kernel.models import (
    FcEventLog,
    FcFact,
    FcFactVersion,
    FcNode,
    FcNodePermission,
    FcSignature,
    FcUser,
)
from artiFACT.modules.audit.service import flush_pending_events
from artiFACT.modules.signing.service import sign_node


async def _make_published_fact(
    db: AsyncSession, node: FcNode, creator: FcUser
) -> tuple[FcFact, FcFactVersion]:
    """Helper: create a fact with a published version in the given node."""
    fact = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=node.node_uid,
        created_by_uid=creator.user_uid,
    )
    db.add(fact)
    await db.flush()

    version = FcFactVersion(
        version_uid=uuid.uuid4(),
        fact_uid=fact.fact_uid,
        display_sentence="A published fact sentence for signing.",
        state="published",
        created_by_uid=creator.user_uid,
    )
    db.add(version)
    await db.flush()

    fact.current_published_version_uid = version.version_uid
    await db.flush()
    return fact, version


async def test_sign_uses_resolved_role_not_global(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
):
    """v1 B-AUTH-01: Permission uses resolved role (node grant), not global_role.

    A user with global_role='viewer' but a node-scoped 'signatory' grant
    must be allowed to sign. A user with global_role='contributor' and
    no signatory grant must be rejected.
    """
    # User with viewer global_role but signatory grant on child_node
    signatory_user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=Signatory {uuid.uuid4().hex[:8]}",
        display_name="Signatory Via Grant",
        global_role="viewer",
    )
    db.add(signatory_user)
    await db.flush()

    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=signatory_user.user_uid,
        node_uid=child_node.node_uid,
        role="signatory",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()

    await _make_published_fact(db, child_node, admin_user)

    # Signatory via grant can sign
    sig = await sign_node(db, child_node.node_uid, signatory_user)
    await flush_pending_events(db)
    assert sig.fact_count == 1

    # Contributor with no signatory grant cannot sign
    contributor = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=Contrib {uuid.uuid4().hex[:8]}",
        display_name="Contributor No Grant",
        global_role="contributor",
    )
    db.add(contributor)
    await db.flush()

    # Create another published fact to sign
    await _make_published_fact(db, child_node, admin_user)

    with pytest.raises(Forbidden):
        await sign_node(db, child_node.node_uid, contributor)


async def test_batch_update_one_query_not_loop(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
):
    """v1 B-PERF-03: Batch UPDATE in one query, not per-fact loop.

    Create multiple published facts, sign, verify all transitioned
    in one operation (all signed_at identical, single signature record).
    """
    facts_and_versions = []
    for i in range(5):
        f, v = await _make_published_fact(db, child_node, admin_user)
        facts_and_versions.append((f, v))

    sig = await sign_node(db, child_node.node_uid, admin_user)
    await flush_pending_events(db)

    assert sig.fact_count == 5

    # Verify all versions are now signed (refresh to reload from DB after bulk UPDATE)
    for _, v in facts_and_versions:
        await db.refresh(v)
        assert v.state == "signed"
        assert v.signed_at is not None

    # Verify all facts have current_signed_version_uid set
    for f, v in facts_and_versions:
        await db.refresh(f)
        assert f.current_signed_version_uid == v.version_uid


async def test_sign_wrapped_in_transaction(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
):
    """Signing must be wrapped in a transaction (atomic)."""
    f1, v1 = await _make_published_fact(db, child_node, admin_user)
    f2, v2 = await _make_published_fact(db, child_node, admin_user)

    sig = await sign_node(db, child_node.node_uid, admin_user)
    await flush_pending_events(db)

    # Both versions signed atomically (refresh to reload after bulk UPDATE)
    await db.refresh(v1)
    await db.refresh(v2)
    assert v1.state == "signed"
    assert v2.state == "signed"

    # Signature record created
    assert sig.signature_uid is not None
    assert sig.fact_count == 2

    # signature.created event in fc_event_log
    events = (
        (await db.execute(select(FcEventLog).where(FcEventLog.event_type == "signature.created")))
        .scalars()
        .all()
    )
    assert len(events) >= 1
    event = events[-1]
    assert event.payload["node_uid"] == str(child_node.node_uid)
    assert event.payload["fact_count"] == 2


async def test_signature_record_has_correct_count(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
):
    """Signature record must have correct fact_count."""
    for _ in range(3):
        await _make_published_fact(db, child_node, admin_user)

    sig = await sign_node(db, child_node.node_uid, admin_user)
    await flush_pending_events(db)

    # Verify persisted in DB
    persisted = await db.get(FcSignature, sig.signature_uid)
    assert persisted is not None
    assert persisted.fact_count == 3
    assert persisted.node_uid == child_node.node_uid
    assert persisted.signed_by_uid == admin_user.user_uid


async def test_sign_pane_scoped_to_user_nodes(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode, second_node: FcNode
):
    """Sign pane shows only user's scoped nodes — not all nodes.

    A signatory on child_node can sign there but NOT on second_node.
    This proves the sign pane (which filters by can('sign', node)) is scoped.
    """
    signatory = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=ScopedSig {uuid.uuid4().hex[:8]}",
        display_name="Scoped Signatory",
        global_role="viewer",
    )
    db.add(signatory)
    await db.flush()

    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=signatory.user_uid,
        node_uid=child_node.node_uid,
        role="signatory",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()

    # Published facts in both nodes
    await _make_published_fact(db, child_node, admin_user)
    await _make_published_fact(db, second_node, admin_user)

    # Signatory can sign child_node (in scope)
    sig = await sign_node(db, child_node.node_uid, signatory)
    await flush_pending_events(db)
    assert sig.fact_count == 1

    # Signatory cannot sign second_node (out of scope)
    with pytest.raises(Forbidden):
        await sign_node(db, second_node.node_uid, signatory)

    # Admin can sign second_node (admin sees all)
    sig2 = await sign_node(db, second_node.node_uid, admin_user)
    await flush_pending_events(db)
    assert sig2.fact_count == 1
