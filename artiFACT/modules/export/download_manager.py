"""S3 presigned URL generation with user-bound verification."""

import json
from typing import Any

import redis

from artiFACT.kernel.config import settings
from artiFACT.kernel.exceptions import Forbidden, NotFound
from artiFACT.kernel.models import FcUser
from artiFACT.kernel.s3 import get_s3_client


def get_download_url(session_uid: str, actor: FcUser) -> dict[str, Any]:
    """Generate a presigned URL for a completed document.

    Verifies that the requesting user is the one who generated the document.
    URLs expire in 1 hour (3600s).
    """
    r = redis.from_url(settings.REDIS_URL)  # type: ignore[no-untyped-call]  # redis stub gap
    meta_raw = r.get(f"docgen:meta:{session_uid}")
    if not meta_raw:
        raise NotFound("Document not found or expired", code="DOCUMENT_NOT_FOUND")

    meta = json.loads(meta_raw)
    if meta["actor_uid"] != str(actor.user_uid):
        raise Forbidden("You can only download documents you generated", code="DOWNLOAD_FORBIDDEN")

    s3_client = get_s3_client()
    url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": meta["s3_key"]},
        ExpiresIn=3600,
    )

    return {"url": url, "expires_in": 3600}


def get_progress(session_uid: str) -> dict[str, Any] | None:
    """Get current progress for a document generation session."""
    r = redis.from_url(settings.REDIS_URL)  # type: ignore[no-untyped-call]  # redis stub gap
    data = r.get(f"docgen:status:{session_uid}")
    if data:
        return json.loads(data)  # type: ignore[no-any-return]  # JSON parsed data
    return None
