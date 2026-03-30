"""Event bus subscriber — records events to fc_event_log."""

from typing import Any

from artiFACT.kernel.events import subscribe
from artiFACT.kernel.models import FcEventLog

_pending_events: list[FcEventLog] = []


def get_pending_events() -> list[FcEventLog]:
    """Return pending events and clear the buffer."""
    events = list(_pending_events)
    _pending_events.clear()
    return events


def _compute_reverse(event_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Compute reverse_payload for undoable events."""
    if event_type == "fact.retired":
        return {"action": "unretire", "fact_uid": payload["fact_uid"]}
    if event_type == "fact.moved":
        return {
            "action": "move",
            "fact_uid": payload["fact_uid"],
            "target_node_uid": payload["old_node_uid"],
        }
    if event_type in ("version.rejected",):
        return {
            "action": "unreject",
            "version_uid": payload["version_uid"],
            "restore_state": "proposed",
        }
    return None


async def _record_fact_event(payload: dict[str, Any]) -> None:
    """Record a fact-related event."""
    event_type = payload.get("event_type", "fact.created")
    reverse = _compute_reverse(event_type, payload)
    event = FcEventLog(
        entity_type="fact",
        entity_uid=payload["fact_uid"],
        event_type=event_type,
        payload=payload,
        actor_uid=payload.get("actor_uid"),
        reversible=reverse is not None,
        reverse_payload=reverse,
    )
    _pending_events.append(event)


async def _record_fact_created(payload: dict[str, Any]) -> None:
    payload_with_type = {**payload, "event_type": "fact.created"}
    await _record_fact_event(payload_with_type)


async def _record_fact_edited(payload: dict[str, Any]) -> None:
    payload_with_type = {**payload, "event_type": "fact.edited"}
    await _record_fact_event(payload_with_type)


async def _record_fact_retired(payload: dict[str, Any]) -> None:
    payload_with_type = {**payload, "event_type": "fact.retired"}
    await _record_fact_event(payload_with_type)


async def _record_fact_unretired(payload: dict[str, Any]) -> None:
    payload_with_type = {**payload, "event_type": "fact.unretired"}
    await _record_fact_event(payload_with_type)


async def _record_fact_moved(payload: dict[str, Any]) -> None:
    payload_with_type = {**payload, "event_type": "fact.moved"}
    await _record_fact_event(payload_with_type)


async def _record_signature_created(payload: dict[str, Any]) -> None:
    """Record a signature.created event."""
    event = FcEventLog(
        entity_type="signature",
        entity_uid=payload["signature_uid"],
        event_type="signature.created",
        payload=payload,
        actor_uid=payload.get("actor_uid"),
        reversible=False,
        reverse_payload=None,
    )
    _pending_events.append(event)


async def _record_version_event(payload: dict[str, Any]) -> None:
    event_type = f"version.{payload.get('new_state', 'unknown')}"
    reverse = _compute_reverse(event_type, payload)
    event = FcEventLog(
        entity_type="version",
        entity_uid=payload["version_uid"],
        event_type=event_type,
        payload=payload,
        actor_uid=payload.get("actor_uid"),
        reversible=reverse is not None,
        reverse_payload=reverse,
    )
    _pending_events.append(event)


async def _record_comment_created(payload: dict[str, Any]) -> None:
    """Record a comment.created event."""
    event = FcEventLog(
        entity_type="comment",
        entity_uid=payload["comment_uid"],
        event_type="comment.created",
        payload=payload,
        actor_uid=payload.get("actor_uid"),
        reversible=False,
        reverse_payload=None,
    )
    _pending_events.append(event)


async def _record_challenge_event(payload: dict[str, Any], event_type: str) -> None:
    """Record a challenge lifecycle event."""
    event = FcEventLog(
        entity_type="comment",
        entity_uid=payload["comment_uid"],
        event_type=event_type,
        payload=payload,
        actor_uid=payload.get("actor_uid"),
        note=payload.get("note"),
        reversible=False,
        reverse_payload=None,
    )
    _pending_events.append(event)


async def _record_challenge_created(payload: dict[str, Any]) -> None:
    await _record_challenge_event(payload, "challenge.created")


async def _record_challenge_approved(payload: dict[str, Any]) -> None:
    await _record_challenge_event(payload, "challenge.approved")


async def _record_challenge_rejected(payload: dict[str, Any]) -> None:
    await _record_challenge_event(payload, "challenge.rejected")


def register_subscribers() -> None:
    """Register all audit event subscribers. Call at app startup."""
    subscribe("fact.created", _record_fact_created)
    subscribe("fact.edited", _record_fact_edited)
    subscribe("fact.retired", _record_fact_retired)
    subscribe("fact.unretired", _record_fact_unretired)
    subscribe("fact.moved", _record_fact_moved)
    subscribe("version.published", _record_version_event)
    subscribe("version.rejected", _record_version_event)
    subscribe("version.signed", _record_version_event)
    subscribe("signature.created", _record_signature_created)
    subscribe("comment.created", _record_comment_created)
    subscribe("challenge.created", _record_challenge_created)
    subscribe("challenge.approved", _record_challenge_approved)
    subscribe("challenge.rejected", _record_challenge_rejected)
