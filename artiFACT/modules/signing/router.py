"""Signing API endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.db import get_db
from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcUser
from artiFACT.kernel.permissions.resolver import can
from artiFACT.kernel.tree.descendants import get_descendants
from artiFACT.modules.audit.service import flush_pending_events
from artiFACT.modules.signing.schemas import SignatureOut, SignPaneItem, SignRequest
from artiFACT.modules.signing.service import sign_node

router = APIRouter(prefix="/api/v1/signatures", tags=["signing"])


@router.post("/node/{node_uid}")
async def sign_node_endpoint(
    node_uid: uuid.UUID,
    body: SignRequest = SignRequest(),
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Sign all published facts under a node."""
    sig = await sign_node(db, node_uid, user, note=body.note, expires_at=body.expires_at)
    await flush_pending_events(db)
    await db.commit()
    return {
        "status": "signed",
        "data": SignatureOut.model_validate(sig).model_dump(mode="json"),
    }


@router.get("/sign-pane")
async def sign_pane(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """List nodes with unsigned facts scoped to current user."""
    all_nodes_result = await db.execute(select(FcNode).where(FcNode.is_archived.is_(False)))
    all_nodes = list(all_nodes_result.scalars().all())

    items: list[dict[str, Any]] = []
    for node in all_nodes:
        if not await can(user, "sign", node.node_uid, db):
            continue
        descendants = await get_descendants(db, node.node_uid)
        count_stmt = (
            select(func.count())
            .select_from(FcFactVersion)
            .join(FcFact, FcFactVersion.fact_uid == FcFact.fact_uid)
            .where(
                FcFact.node_uid.in_(descendants),
                FcFact.is_retired.is_(False),
                FcFact.current_published_version_uid == FcFactVersion.version_uid,
                FcFactVersion.state == "published",
            )
        )
        result = await db.execute(count_stmt)
        count = result.scalar() or 0
        if count > 0:
            items.append(
                SignPaneItem(
                    node_uid=node.node_uid,
                    node_title=node.title,
                    unsigned_count=count,
                ).model_dump(mode="json")
            )

    return {"data": items, "total": len(items)}
