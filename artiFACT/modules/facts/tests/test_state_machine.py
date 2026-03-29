"""Tests for fact version state machine."""

import uuid
from unittest.mock import patch

import pytest

from artiFACT.kernel.models import FcFactVersion, FcUser
from artiFACT.modules.facts.state_machine import ALLOWED_TRANSITIONS, transition


def _make_version(state: str = "proposed") -> FcFactVersion:
    v = FcFactVersion(
        version_uid=uuid.uuid4(),
        fact_uid=uuid.uuid4(),
        display_sentence="Test sentence for testing.",
        state=state,
        created_by_uid=uuid.uuid4(),
    )
    return v


def _make_actor() -> FcUser:
    return FcUser(
        user_uid=uuid.uuid4(),
        cac_dn="CN=Test Actor",
        display_name="Test Actor",
        global_role="admin",
    )


async def test_proposed_to_published():
    """Valid transition: proposed → published."""
    version = _make_version("proposed")
    actor = _make_actor()
    with patch("artiFACT.modules.facts.state_machine.publish"):
        await transition(version, "published", actor)
    assert version.state == "published"
    assert version.published_at is not None


async def test_signed_cannot_go_to_proposed():
    """Invalid transition: signed → proposed must raise Conflict."""
    from artiFACT.kernel.exceptions import Conflict

    version = _make_version("signed")
    actor = _make_actor()
    with pytest.raises(Conflict):
        await transition(version, "proposed", actor)


async def test_retired_cannot_go_to_published():
    """Invalid transition: retired → published must raise Conflict."""
    from artiFACT.kernel.exceptions import Conflict

    version = _make_version("retired")
    actor = _make_actor()
    with pytest.raises(Conflict):
        await transition(version, "published", actor)


async def test_publish_always_sets_published_at():
    """Regression test for v1 S-BUG-01: published_at must always be set."""
    version = _make_version("proposed")
    actor = _make_actor()
    assert version.published_at is None
    with patch("artiFACT.modules.facts.state_machine.publish"):
        await transition(version, "published", actor)
    assert version.published_at is not None


async def test_sign_sets_signed_at():
    """Signing a version must set signed_at."""
    version = _make_version("published")
    actor = _make_actor()
    assert version.signed_at is None
    with patch("artiFACT.modules.facts.state_machine.publish"):
        await transition(version, "signed", actor)
    assert version.state == "signed"
    assert version.signed_at is not None


async def test_all_terminal_states_reject_transitions():
    """Terminal states (rejected, withdrawn, retired) allow no transitions."""
    actor = _make_actor()
    for terminal_state in ["rejected", "withdrawn", "retired"]:
        version = _make_version(terminal_state)
        assert ALLOWED_TRANSITIONS[terminal_state] == []
        for target in ["proposed", "published", "signed"]:
            from artiFACT.kernel.exceptions import Conflict
            with pytest.raises(Conflict):
                await transition(version, target, actor)
