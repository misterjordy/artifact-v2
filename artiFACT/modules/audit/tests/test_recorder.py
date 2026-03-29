"""Tests for audit event recorder."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcNode, FcUser
from artiFACT.modules.audit.recorder import get_pending_events
from artiFACT.modules.facts.service import create_fact, retire_fact


def _mock_can_admin():
    async def mock_can(user, action, node_uid, db):
        from artiFACT.kernel.permissions.hierarchy import REQUIRED_ROLES, role_gte
        required = REQUIRED_ROLES.get(action)
        if not required:
            return False
        return role_gte(user.global_role, required)
    return mock_can


async def test_event_recorded_on_create(db: AsyncSession, admin_user, child_node):
    """Creating a fact must emit an event captured by the recorder."""
    from artiFACT.modules.audit.recorder import _pending_events
    _pending_events.clear()

    with patch("artiFACT.modules.facts.service.can", side_effect=_mock_can_admin()), \
         patch("artiFACT.modules.facts.versioning.can", side_effect=_mock_can_admin()), \
         patch("artiFACT.modules.facts.service.validate_duplicate", new_callable=AsyncMock):
        fact, version = await create_fact(
            db, child_node.node_uid, "A recorded fact for testing audit.", admin_user
        )

    events = get_pending_events()
    assert len(events) >= 1
    fact_event = [e for e in events if e.entity_type == "fact"]
    assert len(fact_event) >= 1
    assert fact_event[0].event_type == "fact.created"
    assert fact_event[0].actor_uid == str(admin_user.user_uid)


async def test_event_recorded_on_retire(db: AsyncSession, admin_user, child_node):
    """Retiring a fact must emit an event captured by the recorder."""
    from artiFACT.modules.audit.recorder import _pending_events
    _pending_events.clear()

    with patch("artiFACT.modules.facts.service.can", side_effect=_mock_can_admin()), \
         patch("artiFACT.modules.facts.versioning.can", side_effect=_mock_can_admin()), \
         patch("artiFACT.modules.facts.service.validate_duplicate", new_callable=AsyncMock):
        fact, _ = await create_fact(
            db, child_node.node_uid, "A fact to retire for audit test.", admin_user
        )
        await db.flush()

    _pending_events.clear()

    with patch("artiFACT.modules.facts.service.can", side_effect=_mock_can_admin()):
        await retire_fact(db, fact.fact_uid, admin_user)

    events = get_pending_events()
    retire_events = [e for e in events if e.event_type == "fact.retired"]
    assert len(retire_events) == 1
    assert retire_events[0].entity_uid == str(fact.fact_uid)
