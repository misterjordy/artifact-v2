"""Internal event bus (publish/subscribe)."""

from collections.abc import Callable, Coroutine
from typing import Any

EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]

_subscribers: dict[str, list[EventHandler]] = {}


def subscribe(event_type: str, handler: EventHandler) -> None:
    _subscribers.setdefault(event_type, []).append(handler)


async def publish(event_type: str, payload: dict[str, Any]) -> None:
    for handler in _subscribers.get(event_type, []):
        await handler(payload)
