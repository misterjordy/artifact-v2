"""File upload processing: validate, hash, S3 upload, create session."""

import hashlib
from datetime import date
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Conflict, Forbidden
from artiFACT.kernel.models import FcImportSession, FcNode, FcUser
from artiFACT.kernel.permissions.resolver import can

ALLOWED_EXTENSIONS = {"docx", "pptx", "pdf", "txt", "md"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


async def handle_upload(
    db: AsyncSession,
    file: UploadFile,
    program_node_uid: UUID,
    effective_date: date,
    actor: FcUser,
    granularity: str = "standard",
) -> FcImportSession:
    """Validate upload, hash content, store in S3, create session record."""
    if not await can(actor, "contribute", program_node_uid, db):
        raise Forbidden("Cannot import into this node", code="FORBIDDEN")

    node = await db.get(FcNode, program_node_uid)
    if not node:
        raise Forbidden("Node not found", code="NODE_NOT_FOUND")

    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail=f"File too large (max {MAX_FILE_SIZE // (1024 * 1024)} MB)",
        )

    filename = file.filename or "unnamed"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type: .{ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    file_hash = hashlib.sha256(content).hexdigest()

    existing = await db.execute(
        select(FcImportSession).where(
            FcImportSession.source_hash == file_hash,
            FcImportSession.status.in_(["pending", "analyzing", "staged"]),
        )
    )
    if existing.scalar_one_or_none():
        raise Conflict("This file was already uploaded and is pending review")

    s3_key = f"imports/{actor.user_uid}/{file_hash}/{filename}"

    from artiFACT.kernel.s3 import upload_bytes

    upload_bytes(s3_key, content)

    session = FcImportSession(
        program_node_uid=program_node_uid,
        source_filename=filename,
        source_hash=file_hash,
        source_s3_key=s3_key,
        effective_date=effective_date,
        granularity=granularity,
        created_by_uid=actor.user_uid,
    )
    db.add(session)
    await db.flush()

    return session
