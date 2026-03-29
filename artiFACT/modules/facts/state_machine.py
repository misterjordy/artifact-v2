"""Fact version state transitions."""

from datetime import datetime, timezone

from artiFACT.kernel.events import publish
from artiFACT.kernel.exceptions import Conflict
from artiFACT.kernel.models import FcFactVersion, FcUser

ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "proposed": ["published", "rejected", "withdrawn"],
    "challenged": ["accepted", "rejected"],
    "accepted": ["published"],
    "rejected": [],
    "published": ["signed", "retired"],
    "signed": ["retired"],
    "withdrawn": [],
    "retired": [],
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def transition(version: FcFactVersion, new_state: str, actor: FcUser) -> None:
    """Move a version to new_state, enforcing ALLOWED_TRANSITIONS."""
    current = version.state
    allowed = ALLOWED_TRANSITIONS.get(current, [])
    if new_state not in allowed:
        raise Conflict(
            f"Cannot transition from {current} to {new_state}",
            code="INVALID_TRANSITION",
        )

    version.state = new_state

    if new_state == "published":
        version.published_at = _utcnow()
    if new_state == "signed":
        version.signed_at = _utcnow()

    await publish(
        f"version.{new_state}",
        {
            "version_uid": str(version.version_uid),
            "fact_uid": str(version.fact_uid),
            "actor_uid": str(actor.user_uid),
            "old_state": current,
            "new_state": new_state,
        },
    )
