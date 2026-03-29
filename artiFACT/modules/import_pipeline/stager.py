"""Stage extracted facts for user review — write staged JSON to S3."""

import json
from typing import Any, cast
from uuid import UUID

from artiFACT.kernel.s3 import download_json, upload_json


def stage_facts(session_uid: UUID, facts: list[dict[str, Any]]) -> str:
    """Write staged facts JSON to S3 and return the S3 key."""
    staged_key = f"imports/{session_uid}/staged.json"
    staged = [
        {
            "index": i,
            "sentence": f.get("sentence", ""),
            "metadata_tags": f.get("metadata_tags", []),
            "source_reference": f.get("source_reference"),
            "duplicate_of": f.get("duplicate_of"),
            "similarity": f.get("similarity"),
            "accepted": True,
        }
        for i, f in enumerate(facts)
    ]
    upload_json(staged_key, json.dumps(staged))
    return staged_key


def load_staged_facts(s3_key: str) -> list[dict[str, Any]]:
    """Load staged facts from S3."""
    return cast(list[dict[str, Any]], json.loads(download_json(s3_key)))
