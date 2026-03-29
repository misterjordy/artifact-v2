"""Pre-check if an undo operation is safe (no state drift)."""

from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Conflict, NotFound
from artiFACT.kernel.models import FcEventLog, FcFact, FcFactVersion


async def check_collision(db: AsyncSession, event: FcEventLog) -> None:
    """Verify the entity is still in the expected state for undo."""
    reverse = event.reverse_payload
    if not reverse:
        raise Conflict("Event has no reverse payload", code="NOT_REVERSIBLE")

    action = reverse.get("action")

    if action == "unretire":
        fact = await db.get(FcFact, reverse["fact_uid"])
        if not fact:
            raise NotFound("Fact no longer exists", code="ENTITY_GONE")
        if not fact.is_retired:
            raise Conflict(
                "Fact is no longer retired — state has changed",
                code="COLLISION_DETECTED",
            )

    elif action == "move":
        fact = await db.get(FcFact, reverse["fact_uid"])
        if not fact:
            raise NotFound("Fact no longer exists", code="ENTITY_GONE")

    elif action == "unreject":
        version = await db.get(FcFactVersion, reverse["version_uid"])
        if not version:
            raise NotFound("Version no longer exists", code="ENTITY_GONE")
        if version.state != "rejected":
            raise Conflict(
                "Version is no longer rejected — state has changed",
                code="COLLISION_DETECTED",
            )
