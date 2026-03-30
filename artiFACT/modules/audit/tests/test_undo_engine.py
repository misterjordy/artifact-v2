"""Tests for undo engine — core undo, collision, bulk grouping, and actions list."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Conflict, Forbidden, NotFound
from artiFACT.kernel.models import (
    FcEventLog,
    FcFact,
    FcFactComment,
    FcFactVersion,
    FcNode,
    FcNodePermission,
    FcUser,
)
from artiFACT.modules.audit.service import flush_pending_events
from artiFACT.modules.audit.undo_engine import undo_bulk, undo_event
from artiFACT.modules.facts.service import create_fact, edit_fact, retire_fact, unretire_fact
from artiFACT.modules.facts.reassign import reassign_fact
from artiFACT.modules.taxonomy.service import archive_node, create_node


# ── Helpers ──


async def _flush(db: AsyncSession) -> list[FcEventLog]:
    """Flush pending audit events and return them."""
    events = await flush_pending_events(db)
    await db.flush()
    return events


def _find_event(events: list[FcEventLog], event_type: str) -> FcEventLog:
    """Find the first event matching the given type."""
    for e in events:
        if e.event_type == event_type:
            return e
    raise AssertionError(f"No event with type {event_type} found in {[e.event_type for e in events]}")


# ── Core undo tests ──


async def test_undo_retired_fact(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
) -> None:
    """Undoing a retire should unretire the fact."""
    fact, _ = await create_fact(
        db, child_node.node_uid,
        f"Retire undo test {uuid.uuid4().hex[:8]}.", admin_user,
    )
    await db.flush()
    await _flush(db)

    await retire_fact(db, fact.fact_uid, admin_user)
    await db.flush()
    events = await _flush(db)
    retire_event = _find_event(events, "fact.retired")

    assert retire_event.reversible is True
    assert retire_event.reverse_payload["action"] == "unretire"

    result = await undo_event(db, retire_event.event_uid, admin_user)
    await db.flush()

    assert result["status"] == "undone"

    await db.refresh(fact)
    assert fact.is_retired is False

    await db.refresh(retire_event)
    assert retire_event.undone_at is not None
    assert retire_event.undone_by_uid == admin_user.user_uid

    # An undo audit event should exist
    stmt = select(FcEventLog).where(
        FcEventLog.event_type == "undo",
        FcEventLog.payload["original_event_uid"].astext == str(retire_event.event_uid),
    )
    undo_audit = (await db.execute(stmt)).scalar_one_or_none()
    assert undo_audit is not None


async def test_undo_fact_move(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode, second_node: FcNode,
) -> None:
    """Undoing a move should move the fact back."""
    fact, _ = await create_fact(
        db, child_node.node_uid,
        f"Move undo test {uuid.uuid4().hex[:8]}.", admin_user,
    )
    await db.flush()
    await _flush(db)

    await reassign_fact(db, fact.fact_uid, second_node.node_uid, admin_user)
    await db.flush()
    events = await _flush(db)
    move_event = _find_event(events, "fact.moved")

    assert move_event.reversible is True
    assert move_event.reverse_payload["action"] == "move_back"

    result = await undo_event(db, move_event.event_uid, admin_user)
    await db.flush()

    assert result["status"] == "undone"
    await db.refresh(fact)
    assert fact.node_uid == child_node.node_uid


async def test_undo_fact_edit(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
) -> None:
    """Undoing an edit should restore the previous version as current."""
    fact, v1 = await create_fact(
        db, child_node.node_uid,
        f"Original sentence {uuid.uuid4().hex[:8]}.", admin_user,
        auto_approve=True,
    )
    await db.flush()
    await _flush(db)

    fact2, v2 = await edit_fact(
        db, fact.fact_uid,
        f"Edited sentence {uuid.uuid4().hex[:8]}.", admin_user,
        auto_approve=True,
    )
    await db.flush()
    events = await _flush(db)
    edit_event = _find_event(events, "fact.edited")

    assert edit_event.reversible is True
    assert edit_event.reverse_payload["action"] == "restore_version"
    assert edit_event.reverse_payload["previous_version_uid"] == str(v1.version_uid)

    result = await undo_event(db, edit_event.event_uid, admin_user)
    await db.flush()

    assert result["status"] == "undone"
    await db.refresh(fact)
    assert fact.current_published_version_uid == v1.version_uid


async def test_undo_node_create(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode,
) -> None:
    """Undoing a node creation should archive the node."""
    node = await create_node(db, f"Undo Node {uuid.uuid4().hex[:8]}", root_node.node_uid, 0, admin_user)
    await db.flush()
    events = await _flush(db)
    create_event = _find_event(events, "node.created")

    assert create_event.reversible is True
    assert create_event.reverse_payload["action"] == "archive_node"

    result = await undo_event(db, create_event.event_uid, admin_user)
    await db.flush()

    assert result["status"] == "undone"
    await db.refresh(node)
    assert node.is_archived is True


async def test_undo_comment(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
) -> None:
    """Undoing a comment should delete it."""
    fact, version = await create_fact(
        db, child_node.node_uid,
        f"Comment undo test {uuid.uuid4().hex[:8]}.", admin_user,
    )
    await db.flush()
    await _flush(db)

    comment = FcFactComment(
        comment_uid=uuid.uuid4(),
        version_uid=version.version_uid,
        body="Test comment for undo",
        comment_type="comment",
        created_by_uid=admin_user.user_uid,
    )
    db.add(comment)
    await db.flush()

    # Manually create the event (comment.created is published by router, not service)
    from artiFACT.kernel.events import publish
    await publish("comment.created", {
        "comment_uid": str(comment.comment_uid),
        "version_uid": str(version.version_uid),
        "actor_uid": str(admin_user.user_uid),
    })
    events = await _flush(db)
    comment_event = _find_event(events, "comment.created")

    assert comment_event.reversible is True
    assert comment_event.reverse_payload["action"] == "delete_comment"

    result = await undo_event(db, comment_event.event_uid, admin_user)
    await db.flush()

    assert result["status"] == "undone"
    deleted = await db.get(FcFactComment, comment.comment_uid)
    assert deleted is None


async def test_undo_permission_grant(
    db: AsyncSession, admin_user: FcUser, contributor_user: FcUser, child_node: FcNode,
) -> None:
    """Undoing a grant should revoke the permission."""
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=contributor_user.user_uid,
        node_uid=child_node.node_uid,
        role="contributor",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()

    from artiFACT.kernel.events import publish
    await publish("grant.created", {
        "permission_uid": str(perm.permission_uid),
        "user_uid": str(contributor_user.user_uid),
        "node_uid": str(child_node.node_uid),
        "role": "contributor",
        "actor_uid": str(admin_user.user_uid),
    })
    events = await _flush(db)
    grant_event = _find_event(events, "grant.created")

    assert grant_event.reversible is True

    result = await undo_event(db, grant_event.event_uid, admin_user)
    await db.flush()

    assert result["status"] == "undone"
    await db.refresh(perm)
    assert perm.revoked_at is not None


# ── Collision / lock tests ──


async def test_undo_blocked_when_entity_modified_by_another_user(
    db: AsyncSession, admin_user: FcUser, approver_user: FcUser, child_node: FcNode,
    approver_permission: FcNodePermission,
) -> None:
    """Undo should fail if entity state changed."""
    fact, _ = await create_fact(
        db, child_node.node_uid,
        f"Collision test {uuid.uuid4().hex[:8]}.", admin_user,
    )
    await db.flush()
    await _flush(db)

    await retire_fact(db, fact.fact_uid, admin_user)
    await db.flush()
    events = await _flush(db)
    retire_event = _find_event(events, "fact.retired")

    # Another user unretires
    await unretire_fact(db, fact.fact_uid, approver_user)
    await db.flush()
    await _flush(db)

    with pytest.raises(Conflict, match="state has changed"):
        await undo_event(db, retire_event.event_uid, admin_user)


async def test_undo_blocked_for_non_reversible_event(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
) -> None:
    """Non-reversible events cannot be undone."""
    event = FcEventLog(
        event_uid=uuid.uuid4(),
        entity_type="fact",
        entity_uid=uuid.uuid4(),
        event_type="fact.published",
        actor_uid=str(admin_user.user_uid),
        reversible=False,
        reverse_payload=None,
    )
    db.add(event)
    await db.flush()

    with pytest.raises(Conflict, match="not reversible"):
        await undo_event(db, event.event_uid, admin_user)


async def test_undo_blocked_for_other_users_event(
    db: AsyncSession, admin_user: FcUser, contributor_user: FcUser, child_node: FcNode,
) -> None:
    """Users cannot undo actions performed by others."""
    fact, _ = await create_fact(
        db, child_node.node_uid,
        f"Other user undo test {uuid.uuid4().hex[:8]}.", admin_user,
    )
    await db.flush()
    await _flush(db)

    await retire_fact(db, fact.fact_uid, admin_user)
    await db.flush()
    events = await _flush(db)
    retire_event = _find_event(events, "fact.retired")

    with pytest.raises(Forbidden, match="only undo your own"):
        await undo_event(db, retire_event.event_uid, contributor_user)


async def test_undo_blocked_when_already_undone(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
) -> None:
    """Cannot undo the same event twice."""
    fact, _ = await create_fact(
        db, child_node.node_uid,
        f"Double undo test {uuid.uuid4().hex[:8]}.", admin_user,
    )
    await db.flush()
    await _flush(db)

    await retire_fact(db, fact.fact_uid, admin_user)
    await db.flush()
    events = await _flush(db)
    retire_event = _find_event(events, "fact.retired")

    await undo_event(db, retire_event.event_uid, admin_user)
    await db.flush()

    with pytest.raises(Conflict, match="Already undone"):
        await undo_event(db, retire_event.event_uid, admin_user)


async def test_undo_blocked_when_permission_lost(
    db: AsyncSession, approver_user: FcUser, admin_user: FcUser,
    child_node: FcNode, approver_permission: FcNodePermission,
) -> None:
    """Undo should fail if user lost permission since the action."""
    fact, _ = await create_fact(
        db, child_node.node_uid,
        f"Perm loss undo test {uuid.uuid4().hex[:8]}.", approver_user,
    )
    await db.flush()
    await _flush(db)

    await retire_fact(db, fact.fact_uid, approver_user)
    await db.flush()
    events = await _flush(db)
    retire_event = _find_event(events, "fact.retired")

    # Revoke permission and downgrade role
    approver_permission.revoked_at = datetime.now(timezone.utc)
    approver_user.global_role = "viewer"
    await db.flush()

    # Invalidate permission cache so resolver sees the revocation
    from artiFACT.kernel.permissions.cache import invalidate_user_permissions
    await invalidate_user_permissions(approver_user.user_uid)

    with pytest.raises(Forbidden, match="no longer have permission"):
        await undo_event(db, retire_event.event_uid, approver_user)


# ── Undo actions list tests ──


async def test_undo_actions_returns_30_days(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
) -> None:
    """Only events from last 30 days are returned."""
    from artiFACT.modules.audit.undo_actions import get_undo_actions

    fact, _ = await create_fact(
        db, child_node.node_uid,
        f"Recent {uuid.uuid4().hex[:8]}.", admin_user,
    )
    await db.flush()
    events = await _flush(db)

    # Create an old event manually (>30 days)
    old_event = FcEventLog(
        event_uid=uuid.uuid4(),
        entity_type="fact",
        entity_uid=fact.fact_uid,
        event_type="fact.retired",
        actor_uid=str(admin_user.user_uid),
        occurred_at=datetime.now(timezone.utc) - timedelta(days=35),
        reversible=True,
        reverse_payload={"action": "unretire", "fact_uid": str(fact.fact_uid)},
    )
    db.add(old_event)
    await db.flush()

    actions = await get_undo_actions(db, admin_user, days=30)

    action_uids = {a.event_uid for a in actions}
    assert old_event.event_uid not in action_uids
    assert any(e.event_uid in action_uids for e in events)


async def test_undo_actions_shows_all_event_types(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
) -> None:
    """Both undoable and non-undoable events appear in the list."""
    from artiFACT.modules.audit.undo_actions import get_undo_actions

    fact, _ = await create_fact(
        db, child_node.node_uid,
        f"Mixed types {uuid.uuid4().hex[:8]}.", admin_user,
    )
    await db.flush()
    await _flush(db)

    await retire_fact(db, fact.fact_uid, admin_user)
    await db.flush()
    await _flush(db)

    # Also add a non-reversible event
    non_rev = FcEventLog(
        event_uid=uuid.uuid4(),
        entity_type="fact",
        entity_uid=fact.fact_uid,
        event_type="fact.published",
        actor_uid=str(admin_user.user_uid),
        reversible=False,
    )
    db.add(non_rev)
    await db.flush()

    actions = await get_undo_actions(db, admin_user)
    types = {a.event_type for a in actions}
    assert "fact.retired" in types
    assert "fact.published" in types

    non_rev_action = next(a for a in actions if a.event_type == "fact.published")
    assert non_rev_action.is_undoable is False
    assert non_rev_action.lock_reason is not None


async def test_undo_actions_includes_descriptions(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
) -> None:
    """Actions include descriptions and entity detail."""
    from artiFACT.modules.audit.undo_actions import get_undo_actions

    sentence = f"A described fact {uuid.uuid4().hex[:8]}."
    fact, _ = await create_fact(db, child_node.node_uid, sentence, admin_user)
    await db.flush()
    await _flush(db)

    actions = await get_undo_actions(db, admin_user)
    assert len(actions) >= 1
    action = actions[0]
    assert action.description != ""
    assert action.occurred_at is not None


async def test_undo_actions_only_shows_own_actions(
    db: AsyncSession, admin_user: FcUser, approver_user: FcUser,
    child_node: FcNode, approver_permission: FcNodePermission,
) -> None:
    """Each user only sees their own actions."""
    from artiFACT.modules.audit.undo_actions import get_undo_actions

    fact_a, _ = await create_fact(
        db, child_node.node_uid,
        f"Admin fact {uuid.uuid4().hex[:8]}.", admin_user,
    )
    await db.flush()
    await _flush(db)

    fact_b, _ = await create_fact(
        db, child_node.node_uid,
        f"Approver fact {uuid.uuid4().hex[:8]}.", approver_user,
    )
    await db.flush()
    await _flush(db)

    admin_actions = await get_undo_actions(db, admin_user)
    approver_actions = await get_undo_actions(db, approver_user)

    admin_uids = {a.event_uid for a in admin_actions}
    approver_uids = {a.event_uid for a in approver_actions}
    assert admin_uids.isdisjoint(approver_uids)


# ── Bulk grouping tests ──


async def test_bulk_grouping_5_plus_events(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
) -> None:
    """7 retires within 30 seconds should group into one bulk line."""
    from artiFACT.modules.audit.undo_actions import get_undo_actions

    base_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    facts = []
    for i in range(7):
        f, _ = await create_fact(
            db, child_node.node_uid,
            f"Bulk fact {i} {uuid.uuid4().hex[:8]}.", admin_user,
        )
        await db.flush()
        facts.append(f)
    await _flush(db)

    for i, f in enumerate(facts):
        await retire_fact(db, f.fact_uid, admin_user)
        await db.flush()
    events = await _flush(db)

    # Set timestamps within 30s window
    retire_events = [e for e in events if e.event_type == "fact.retired"]
    for i, ev in enumerate(retire_events):
        ev.occurred_at = base_time + timedelta(seconds=i * 3)
    await db.flush()

    actions = await get_undo_actions(db, admin_user)
    bulk_lines = [a for a in actions if a.is_bulk]
    assert len(bulk_lines) >= 1
    bulk = bulk_lines[0]
    assert bulk.bulk_count == 7
    assert len(bulk.bulk_event_uids) == 7


async def test_bulk_grouping_under_5_not_grouped(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
) -> None:
    """3 retires within 30 seconds should NOT be grouped."""
    from artiFACT.modules.audit.undo_actions import get_undo_actions

    base_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    facts = []
    for i in range(3):
        f, _ = await create_fact(
            db, child_node.node_uid,
            f"Small group {i} {uuid.uuid4().hex[:8]}.", admin_user,
        )
        await db.flush()
        facts.append(f)
    await _flush(db)

    for f in facts:
        await retire_fact(db, f.fact_uid, admin_user)
        await db.flush()
    events = await _flush(db)

    retire_events = [e for e in events if e.event_type == "fact.retired"]
    for i, ev in enumerate(retire_events):
        ev.occurred_at = base_time + timedelta(seconds=i * 3)
    await db.flush()

    actions = await get_undo_actions(db, admin_user)
    bulk_lines = [a for a in actions if a.is_bulk and a.event_type == "fact.retired"]
    assert len(bulk_lines) == 0


async def test_bulk_undo_reverts_all(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
) -> None:
    """Bulk undo should revert all events in the group."""
    facts = []
    event_uids = []
    for i in range(5):
        f, _ = await create_fact(
            db, child_node.node_uid,
            f"Bulk undo {i} {uuid.uuid4().hex[:8]}.", admin_user,
        )
        await db.flush()
        facts.append(f)
    await _flush(db)

    for f in facts:
        await retire_fact(db, f.fact_uid, admin_user)
        await db.flush()
    events = await _flush(db)

    retire_events = [e for e in events if e.event_type == "fact.retired"]
    event_uids = [e.event_uid for e in retire_events]

    result = await undo_bulk(db, event_uids, admin_user)
    await db.flush()

    assert result["status"] == "undone"
    assert result["count"] == 5

    for f in facts:
        await db.refresh(f)
        assert f.is_retired is False

    for uid in event_uids:
        ev = await db.get(FcEventLog, uid)
        assert ev.undone_at is not None


async def test_individual_undo_within_bulk_group(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
) -> None:
    """Undoing one event from a group should only affect that one."""
    facts = []
    for i in range(5):
        f, _ = await create_fact(
            db, child_node.node_uid,
            f"Individual undo {i} {uuid.uuid4().hex[:8]}.", admin_user,
        )
        await db.flush()
        facts.append(f)
    await _flush(db)

    for f in facts:
        await retire_fact(db, f.fact_uid, admin_user)
        await db.flush()
    events = await _flush(db)

    retire_events = [e for e in events if e.event_type == "fact.retired"]

    # Undo just the first one
    await undo_event(db, retire_events[0].event_uid, admin_user)
    await db.flush()

    await db.refresh(facts[0])
    assert facts[0].is_retired is False

    for f in facts[1:]:
        await db.refresh(f)
        assert f.is_retired is True


async def test_bulk_undo_blocked_if_any_event_locked(
    db: AsyncSession, admin_user: FcUser, approver_user: FcUser,
    child_node: FcNode, approver_permission: FcNodePermission,
) -> None:
    """Bulk undo fails atomically if any event has a collision."""
    facts = []
    for i in range(5):
        f, _ = await create_fact(
            db, child_node.node_uid,
            f"Bulk lock {i} {uuid.uuid4().hex[:8]}.", admin_user,
        )
        await db.flush()
        facts.append(f)
    await _flush(db)

    for f in facts:
        await retire_fact(db, f.fact_uid, admin_user)
        await db.flush()
    events = await _flush(db)
    retire_events = [e for e in events if e.event_type == "fact.retired"]

    # Another user modifies one entity
    await unretire_fact(db, facts[2].fact_uid, approver_user)
    await db.flush()
    await _flush(db)

    event_uids = [e.event_uid for e in retire_events]
    with pytest.raises(Conflict, match="state has changed"):
        await undo_bulk(db, event_uids, admin_user)


# ── Regression tests ──


def test_no_public_undo_record_endpoint() -> None:
    """Regression: no endpoint accepts arbitrary reverse_payload (U-SEC-01)."""
    import ast
    from pathlib import Path

    router_path = Path(__file__).resolve().parent.parent / "router.py"
    source = router_path.read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if "undo" in node.name:
                for arg in node.args.args:
                    assert arg.arg != "reverse_payload", \
                        "Undo endpoint must not accept reverse_payload from client"


async def test_undo_unretire(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
) -> None:
    """Undoing an unretire should re-retire the fact."""
    fact, _ = await create_fact(
        db, child_node.node_uid,
        f"Unretire undo test {uuid.uuid4().hex[:8]}.", admin_user,
    )
    await db.flush()
    await _flush(db)

    await retire_fact(db, fact.fact_uid, admin_user)
    await db.flush()
    await _flush(db)

    await unretire_fact(db, fact.fact_uid, admin_user)
    await db.flush()
    events = await _flush(db)
    unretire_event = _find_event(events, "fact.unretired")

    assert unretire_event.reversible is True
    assert unretire_event.reverse_payload["action"] == "retire"

    result = await undo_event(db, unretire_event.event_uid, admin_user)
    await db.flush()

    assert result["status"] == "undone"
    await db.refresh(fact)
    assert fact.is_retired is True
