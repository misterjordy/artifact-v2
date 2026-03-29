"""Scope enforcement regression tests (v1 Q-SEC-01, Q-SEC-02, Q-AUTH-02)."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Forbidden
from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcNodePermission, FcUser
from artiFACT.modules.queue.service import approve_proposal, reject_proposal


async def _make_proposed_fact(
    db: AsyncSession, node: FcNode, creator: FcUser
) -> tuple[FcFact, FcFactVersion]:
    """Helper: create a fact with a proposed version in the given node."""
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
        display_sentence="Test proposed sentence for queue.",
        state="proposed",
        created_by_uid=creator.user_uid,
    )
    db.add(version)
    await db.flush()
    return fact, version


async def test_subapprover_cannot_approve_outside_scope(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode, second_node: FcNode
):
    """v1 Q-SEC-01: Subapprover on Node A CANNOT approve proposals from Node B."""
    subapprover = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=SubA {uuid.uuid4().hex[:8]}",
        display_name="SubA",
        global_role="viewer",
    )
    db.add(subapprover)
    await db.flush()

    # Grant subapprover on child_node only
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=subapprover.user_uid,
        node_uid=child_node.node_uid,
        role="subapprover",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()

    # Create proposal in second_node (outside scope)
    _, version = await _make_proposed_fact(db, second_node, admin_user)

    with pytest.raises(Forbidden, match="outside your approval scope"):
        await approve_proposal(db, version.version_uid, subapprover)


async def test_subapprover_cannot_reject_outside_scope(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode, second_node: FcNode
):
    """v1 Q-SEC-01: Subapprover on Node A CANNOT reject proposals from Node B."""
    subapprover = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=SubR {uuid.uuid4().hex[:8]}",
        display_name="SubR",
        global_role="viewer",
    )
    db.add(subapprover)
    await db.flush()

    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=subapprover.user_uid,
        node_uid=child_node.node_uid,
        role="subapprover",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()

    _, version = await _make_proposed_fact(db, second_node, admin_user)

    with pytest.raises(Forbidden, match="outside your approval scope"):
        await reject_proposal(db, version.version_uid, subapprover)


async def test_move_reject_requires_scope_check(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode, second_node: FcNode
):
    """v1 Q-SEC-02: Move rejection must check scope on target node."""
    from artiFACT.kernel.models import FcEventLog
    from artiFACT.modules.queue.service import reject_move

    subapprover = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=SubM {uuid.uuid4().hex[:8]}",
        display_name="SubM",
        global_role="viewer",
    )
    db.add(subapprover)
    await db.flush()

    # Grant on child_node only
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=subapprover.user_uid,
        node_uid=child_node.node_uid,
        role="subapprover",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()

    # Create move proposal targeting second_node (outside scope)
    fact = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=child_node.node_uid,
        created_by_uid=admin_user.user_uid,
    )
    db.add(fact)
    await db.flush()

    event = FcEventLog(
        event_uid=uuid.uuid4(),
        entity_type="fact",
        entity_uid=fact.fact_uid,
        event_type="fact.move_proposed",
        payload={
            "fact_uid": str(fact.fact_uid),
            "target_node_uid": str(second_node.node_uid),
        },
        actor_uid=admin_user.user_uid,
    )
    db.add(event)
    await db.flush()

    with pytest.raises(Forbidden, match="outside your approval scope"):
        await reject_move(db, event.event_uid, subapprover)


async def test_contributor_with_node_grant_can_approve(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
):
    """v1 Q-AUTH-02: A global contributor with subapprover grant on a node can approve."""
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=ContribGrant {uuid.uuid4().hex[:8]}",
        display_name="Contrib With Grant",
        global_role="contributor",
    )
    db.add(user)
    await db.flush()

    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=user.user_uid,
        node_uid=child_node.node_uid,
        role="subapprover",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()

    _, version = await _make_proposed_fact(db, child_node, admin_user)

    result = await approve_proposal(db, version.version_uid, user)

    assert result.state == "published"
