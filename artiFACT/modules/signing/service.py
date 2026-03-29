"""Sign logic — permission check, batch update, signature record, event."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.events import publish
from artiFACT.kernel.exceptions import Conflict, Forbidden
from artiFACT.kernel.models import FcSignature, FcUser
from artiFACT.kernel.permissions.resolver import can
from artiFACT.kernel.tree.descendants import get_descendants
from artiFACT.modules.signing.batch_signer import batch_sign_versions, get_published_versions


async def sign_node(
    db: AsyncSession,
    node_uid: uuid.UUID,
    actor: FcUser,
    *,
    note: str | None = None,
    expires_at: datetime | None = None,
) -> FcSignature:
    """Sign all published facts under a node.

    Permission: kernel/permissions.can('sign', node_uid) — uses resolved role.
    Batch UPDATE in one query inside transaction.
    Creates fc_signature record with fact count.
    Emits signature.created event.
    """
    if not await can(actor, "sign", node_uid, db):
        raise Forbidden("No signatory permission on this node")

    descendants = await get_descendants(db, node_uid)
    versions = await get_published_versions(db, descendants)

    if not versions:
        raise Conflict("No published facts to sign")

    async with db.begin_nested():
        await batch_sign_versions(db, versions)

        sig = FcSignature(
            node_uid=node_uid,
            signed_by_uid=actor.user_uid,
            fact_count=len(versions),
            note=note,
            expires_at=expires_at,
        )
        db.add(sig)

    await publish(
        "signature.created",
        {
            "signature_uid": str(sig.signature_uid),
            "node_uid": str(node_uid),
            "actor_uid": str(actor.user_uid),
            "fact_count": len(versions),
        },
    )

    return sig
