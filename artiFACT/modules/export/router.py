"""Export module API endpoints — ALL routes require auth."""

import json
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.db import get_db
from artiFACT.kernel.exceptions import Forbidden
from artiFACT.kernel.models import FcUser
from artiFACT.kernel.permissions.resolver import can
from artiFACT.modules.export.download_manager import get_download_url, get_progress
from artiFACT.modules.export.factsheet import export_facts
from artiFACT.modules.export.schemas import (
    DeltaFeedOut,
    DocumentOut,
    DocumentRequest,
    DownloadURL,
    TemplateCreate,
    TemplateOut,
    TemplateUpdate,
    ViewsOut,
    ViewsRequest,
)
from artiFACT.modules.export.sync import get_delta_feed, get_full_dump
from artiFACT.modules.export.template_manager import (
    create_template,
    delete_template,
    get_template,
    list_templates,
    update_template,
)
from artiFACT.kernel.access_logger import log_data_access
from artiFACT.modules.admin.anomaly_detector import check_anomaly
from artiFACT.modules.export.docgen.orchestrator import generate_document
from artiFACT.modules.export.views import preview_assignments

router = APIRouter(prefix="/api/v1/export", tags=["export"])
sync_router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


# ── Factsheet endpoints ──


@router.get("/factsheet")
async def export_factsheet(
    node_uids: str = Query(..., description="Comma-separated node UIDs"),
    format: str = Query("json", pattern="^(txt|json|ndjson|csv)$"),
    state: str = Query("published", description="Comma-separated states"),
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export facts as TXT/JSON/NDJSON/CSV."""
    uid_list = [uuid.UUID(u.strip()) for u in node_uids.split(",")]
    state_list = [s.strip() for s in state.split(",")]

    content_types = {
        "txt": "text/plain",
        "json": "application/json",
        "ndjson": "application/x-ndjson",
        "csv": "text/csv",
    }

    stream = await export_facts(db, format, uid_list, state_list, user)

    # ZT Pillar 5: log data access
    await log_data_access(
        db,
        user.user_uid,
        "export",
        {
            "format": format,
            "node_uids": [str(u) for u in uid_list],
        },
    )
    await check_anomaly(db, user.user_uid, "export")

    return StreamingResponse(
        stream,
        media_type=content_types.get(format, "application/json"),
        headers={"Content-Disposition": f'attachment; filename="factsheet.{format}"'},
    )


# ── Document generation endpoints ──


@router.post("/document", response_model=DocumentOut, status_code=202)
async def trigger_document_generation(
    body: DocumentRequest,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    """Trigger DOCX generation as a background task."""
    has_access = False
    for uid in body.node_uids:
        if await can(user, "read", uid, db):
            has_access = True
            break
    if not has_access:
        raise Forbidden("No read access to any of the requested nodes")

    # Verify template exists
    await get_template(db, body.template_uid)

    session_uid = uuid.uuid4()
    generate_document.delay(
        str(session_uid),
        [str(u) for u in body.node_uids],
        str(body.template_uid),
        str(user.user_uid),
    )

    return DocumentOut(session_uid=session_uid, status="processing")


@router.get("/document/{session_uid}/progress")
async def document_progress(
    session_uid: uuid.UUID,
    user: FcUser = Depends(get_current_user),
) -> StreamingResponse:
    """SSE endpoint for document generation progress."""
    import redis as redis_lib

    from artiFACT.kernel.config import settings

    async def event_stream():
        r = redis_lib.from_url(settings.REDIS_URL)
        pubsub = r.pubsub()
        pubsub.subscribe(f"docgen:{session_uid}")

        # Send current status first
        current = get_progress(str(session_uid))
        if current:
            yield f"data: {json.dumps(current)}\n\n"
            if current.get("percent", 0) >= 100:
                return

        for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                yield f"data: {json.dumps(data)}\n\n"
                if data.get("percent", 0) >= 100:
                    break

        pubsub.unsubscribe()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/document/{session_uid}/download", response_model=DownloadURL)
async def download_document(
    session_uid: uuid.UUID,
    user: FcUser = Depends(get_current_user),
) -> DownloadURL:
    """Get signed S3 URL for a completed document. User-bound."""
    result = get_download_url(str(session_uid), user)
    return DownloadURL(**result)


# ── Template CRUD endpoints ──


@router.get("/templates", response_model=list[TemplateOut])
async def list_document_templates(
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TemplateOut]:
    """List active document templates."""
    templates = await list_templates(db)
    return [TemplateOut.model_validate(t) for t in templates]


@router.get("/templates/{template_uid}", response_model=TemplateOut)
async def get_document_template(
    template_uid: uuid.UUID,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TemplateOut:
    """Get a single document template."""
    tpl = await get_template(db, template_uid)
    return TemplateOut.model_validate(tpl)


@router.post("/templates", response_model=TemplateOut, status_code=201)
async def create_document_template(
    body: TemplateCreate,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TemplateOut:
    """Create a new document template (admin only)."""
    if user.global_role != "admin":
        raise Forbidden("Only admins can create templates")
    tpl = await create_template(
        db,
        name=body.name,
        abbreviation=body.abbreviation,
        sections=[s.model_dump() for s in body.sections],
        actor=user,
        description=body.description,
    )
    await db.commit()
    return TemplateOut.model_validate(tpl)


@router.put("/templates/{template_uid}", response_model=TemplateOut)
async def update_document_template(
    template_uid: uuid.UUID,
    body: TemplateUpdate,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TemplateOut:
    """Update an existing document template (admin only)."""
    if user.global_role != "admin":
        raise Forbidden("Only admins can update templates")
    updates = body.model_dump(exclude_unset=True)
    if "sections" in updates and updates["sections"] is not None:
        updates["sections"] = [
            s.model_dump() if hasattr(s, "model_dump") else s for s in updates["sections"]
        ]
    tpl = await update_template(db, template_uid, updates)
    await db.commit()
    return TemplateOut.model_validate(tpl)


@router.delete("/templates/{template_uid}", status_code=204)
async def delete_document_template(
    template_uid: uuid.UUID,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete (deactivate) a document template (admin only)."""
    if user.global_role != "admin":
        raise Forbidden("Only admins can delete templates")
    await delete_template(db, template_uid)
    await db.commit()


# ── Views (prefilter preview) ──


@router.post("/views", response_model=ViewsOut)
async def views_preview(
    body: ViewsRequest,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ViewsOut:
    """Run prefilter only — preview which facts would go in each section."""
    result = await preview_assignments(db, body.node_uids, body.template_uid, user)
    return ViewsOut(**result)


# ── Sync endpoints ──


@sync_router.get("/changes", response_model=DeltaFeedOut)
async def delta_feed(
    cursor: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeltaFeedOut:
    """Delta feed for incremental sync. Uses monotonic seq cursor."""
    result = await get_delta_feed(db, cursor, limit)

    # ZT Pillar 5: log sync delta access
    await log_data_access(
        db,
        user.user_uid,
        "sync_delta",
        {
            "cursor": cursor,
            "count": len(result.get("changes", [])),
        },
    )

    return DeltaFeedOut(**result)


@sync_router.get("/full")
async def full_dump(
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Full dump of all entities for emergency export."""
    result = await get_full_dump(db)

    # ZT Pillar 5: log sync full access
    await log_data_access(
        db,
        user.user_uid,
        "sync_full",
        {
            "total_count": len(result.get("facts", [])),
        },
    )

    return result
