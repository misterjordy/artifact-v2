"""Tests for undo engine."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Conflict, Forbidden
from artiFACT.kernel.models import FcEventLog


def _mock_can_contributor():
    async def mock_can(user, action, node_uid, db):
        from artiFACT.kernel.permissions.hierarchy import REQUIRED_ROLES, role_gte

        required = REQUIRED_ROLES.get(action)
        if not required:
            return False
        return role_gte("contributor", required)

    return mock_can


async def test_undo_checks_current_permission(
    db: AsyncSession, approver_user, admin_user, child_node
):
    """Regression test for v1 U-SEC-02: undo must check CURRENT permissions.

    Scenario: approver retires a fact (allowed), then permissions change so they
    can no longer approve. Undo should fail based on CURRENT permission, not
    the permission at event time.
    """
    from artiFACT.modules.facts.service import create_fact, retire_fact

    with patch("artiFACT.modules.facts.service.validate_duplicate", new_callable=AsyncMock):
        fact, _ = await create_fact(
            db, child_node.node_uid, "Fact for undo permission test here.", approver_user
        )
        await db.flush()

    await retire_fact(db, fact.fact_uid, approver_user)
    await db.flush()

    # Event was created by the approver_user
    event = FcEventLog(
        event_uid=uuid.uuid4(),
        entity_type="fact",
        entity_uid=str(fact.fact_uid),
        event_type="fact.retired",
        payload={"fact_uid": str(fact.fact_uid)},
        actor_uid=str(approver_user.user_uid),
        reversible=True,
        reverse_payload={"action": "unretire", "fact_uid": str(fact.fact_uid)},
    )
    db.add(event)
    await db.flush()

    from artiFACT.modules.audit.undo_engine import undo_event

    # Now mock can() to return False — simulating permission downgrade
    with patch("artiFACT.modules.audit.undo_engine.can", side_effect=_mock_can_contributor()):
        with pytest.raises(Forbidden, match="no longer have permission"):
            await undo_event(db, event.event_uid, approver_user)


def test_no_public_undo_record_endpoint():
    """Regression test for v1 U-SEC-01: no endpoint accepts arbitrary reverse_payload.

    Verify that the audit module does NOT expose an endpoint that accepts
    reverse_payload from client input. The undo endpoint only takes an event_uid
    and reads the server-computed reverse_payload from the database.
    """
    import ast
    from pathlib import Path

    router_path = Path(__file__).resolve().parent.parent / "router.py"
    source = router_path.read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            if "undo" in node.name:
                # Check that the function does not accept a body param named reverse_payload
                for arg in node.args.args:
                    assert (
                        arg.arg != "reverse_payload"
                    ), "Undo endpoint must not accept reverse_payload from client"


async def test_collision_detected_on_stale_undo(db: AsyncSession, admin_user, child_node):
    """Undo should fail if entity state has changed since the event."""
    from artiFACT.modules.facts.service import create_fact, retire_fact

    with patch("artiFACT.modules.facts.service.validate_duplicate", new_callable=AsyncMock):
        fact, _ = await create_fact(
            db, child_node.node_uid, "Fact for collision test in audit.", admin_user
        )
        await db.flush()

    await retire_fact(db, fact.fact_uid, admin_user)
    await db.flush()

    event = FcEventLog(
        event_uid=uuid.uuid4(),
        entity_type="fact",
        entity_uid=str(fact.fact_uid),
        event_type="fact.retired",
        payload={"fact_uid": str(fact.fact_uid)},
        actor_uid=str(admin_user.user_uid),
        reversible=True,
        reverse_payload={"action": "unretire", "fact_uid": str(fact.fact_uid)},
    )
    db.add(event)
    await db.flush()

    # Manually unretire to create stale state
    fact.is_retired = False
    fact.retired_at = None
    await db.flush()

    from artiFACT.modules.audit.collision_checker import check_collision

    with pytest.raises(Conflict, match="state has changed"):
        await check_collision(db, event)
