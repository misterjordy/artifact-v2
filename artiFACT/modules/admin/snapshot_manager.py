"""Database snapshot operations: pg_dump to S3 as Celery task."""

import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any

from artiFACT.kernel.background import app as celery_app
from artiFACT.kernel.config import settings
from artiFACT.kernel.s3 import upload_bytes


def _get_pg_url() -> str:
    """Convert async DATABASE_URL to psycopg-compatible form for pg_dump."""
    url = settings.DATABASE_URL
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


@celery_app.task(name="admin.trigger_snapshot")  # type: ignore[misc]  # Celery task decorator is untyped
def trigger_snapshot(actor_uid_str: str) -> dict[str, Any]:
    """Run pg_dump and upload result to S3."""
    uuid.UUID(actor_uid_str)  # validate format
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"snapshots/artifact_{timestamp}.dump"

    result = subprocess.run(
        ["pg_dump", "--no-owner", "--no-acl", "-Fc", _get_pg_url()],
        capture_output=True,
        timeout=300,
    )

    if result.returncode != 0:
        return {
            "filename": filename,
            "size": 0,
            "status": "failed",
            "error": result.stderr.decode()[:500],
        }

    upload_bytes(filename, result.stdout, content_type="application/octet-stream")

    return {
        "filename": filename,
        "size": len(result.stdout),
        "status": "completed",
    }
