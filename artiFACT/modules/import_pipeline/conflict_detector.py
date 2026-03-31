"""AI-powered duplicate + conflict detection (D/C/X) — Jaccard 0.2-0.85 range."""

import json
from collections.abc import Callable
from uuid import UUID

import httpx
import structlog

from artiFACT.kernel.models import FcImportStagedFact
from artiFACT.modules.import_pipeline.prompts import (
    CONFLICT_SYSTEM_PROMPT,
    CONFLICT_USER_TEMPLATE,
)

log = structlog.get_logger()

AI_MODEL = "gpt-4.1"


async def detect_conflicts(
    staged_facts: list[FcImportStagedFact],
    existing_facts: list[tuple[str, UUID]],
    ai_key: str,
    jaccard_fn: Callable[[set[str], set[str]], float],
    tokenize_fn: Callable[[str], set[str]],
) -> list[dict]:
    """Detect duplicates AND contradictions between staged and existing facts.

    Checks pairs with Jaccard similarity between 0.2 and 0.85.
    Above 0.85 = exact duplicate (flagged mechanically). Below 0.2 = too different.
    Uses AI D/C/X classification for the middle range.
    Returns list of dicts with type='duplicate' or type='conflict'.
    """
    existing_tokenized = [
        (sentence, version_uid, tokenize_fn(sentence))
        for sentence, version_uid in existing_facts
    ]

    results: list[dict] = []

    for staged in staged_facts:
        staged_tokens = tokenize_fn(staged.display_sentence)
        candidates: list[tuple[str, UUID, float]] = []

        for sentence, version_uid, ex_tokens in existing_tokenized:
            score = jaccard_fn(staged_tokens, ex_tokens)
            if 0.2 <= score <= 0.85:
                candidates.append((sentence, version_uid, score))

        if not candidates:
            continue

        # Take top 5 by similarity
        candidates.sort(key=lambda c: c[2], reverse=True)
        candidates = candidates[:5]

        match = await _check_dcx_batch(
            staged.display_sentence,
            [(s, uid) for s, uid, _ in candidates],
            ai_key,
        )

        if match:
            results.append({
                "staged_fact_uid": staged.staged_fact_uid,
                "type": match["type"],
                "version_uid": match["version_uid"],
                "reason": match["reason"],
            })

    return results


async def _check_dcx_batch(
    new_fact: str,
    candidates: list[tuple[str, UUID]],
    ai_key: str,
) -> dict | None:
    """Ask AI to classify each candidate as D (duplicate), C (conflict), or X."""
    numbered_existing = "\n".join(
        f"{i + 1}. {sentence}" for i, (sentence, _) in enumerate(candidates)
    )

    user_msg = CONFLICT_USER_TEMPLATE.format(
        new_fact=new_fact,
        numbered_existing=numbered_existing,
    )

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {ai_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": AI_MODEL,
                "messages": [
                    {"role": "system", "content": CONFLICT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "max_tokens": 2048,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()

    content = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(content)

    # Find first D or C result
    for entry in data.get("results", []):
        entry_type = entry.get("type", "X").upper()
        if entry_type in ("D", "C"):
            idx = entry.get("existing", 1) - 1
            if 0 <= idx < len(candidates):
                return {
                    "type": "duplicate" if entry_type == "D" else "conflict",
                    "version_uid": candidates[idx][1],
                    "reason": entry.get("reason", "Detected by AI"),
                }

    return None
