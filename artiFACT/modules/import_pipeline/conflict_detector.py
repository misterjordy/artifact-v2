"""AI-powered duplicate + conflict detection (D/C/X) — uses finddup skill."""

import json
from collections.abc import Callable
from uuid import UUID

import httpx
import structlog

from artiFACT.kernel.models import FcImportStagedFact
from artiFACT.modules.import_pipeline.prompts import load_skill

log = structlog.get_logger()

AI_MODEL = "gpt-4.1"


async def detect_conflicts(
    staged_facts: list[FcImportStagedFact],
    existing_facts: list[tuple[str, UUID]],
    ai_key: str,
    jaccard_fn: Callable[[set[str], set[str]], float],
    tokenize_fn: Callable[[str], set[str]],
) -> list[dict]:
    """Detect duplicates AND contradictions using finddup skill.

    Checks pairs with Jaccard 0.2-0.85. Uses v1-style D/C/X classification.
    Batches multiple new facts with their candidates in one AI call.
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

        candidates.sort(key=lambda c: c[2], reverse=True)
        candidates = candidates[:5]

        match = await _check_dcx(
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


async def _check_dcx(
    new_fact: str,
    candidates: list[tuple[str, UUID]],
    ai_key: str,
) -> dict | None:
    """Ask AI to classify candidates as D/C/X using finddup skill."""
    system_prompt, user_template = load_skill("finddup")

    # Build v1-style comparison block
    lines: list[str] = [f"N1: {new_fact}"]
    for i, (sentence, _) in enumerate(candidates):
        lines.append(f"e{i + 1}: {sentence}")

    user_msg = user_template.format(comparisons="\n".join(lines))

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
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                "max_tokens": 2048,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()

    content = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(content)

    # Parse v1-style: {"r":[{"n":1,"t":"D|C|X","e":"e1","reason":"..."},...]}
    for entry in data.get("r", data.get("results", [])):
        entry_type = entry.get("t", entry.get("type", "X")).upper()
        if entry_type in ("D", "C"):
            # Extract candidate index from e field ("e1" -> 0, "e2" -> 1, etc.)
            e_val = str(entry.get("e", "e1"))
            idx = _parse_candidate_idx(e_val, len(candidates))
            if idx is not None and 0 <= idx < len(candidates):
                return {
                    "type": "duplicate" if entry_type == "D" else "conflict",
                    "version_uid": candidates[idx][1],
                    "reason": entry.get("reason", "Detected by AI"),
                }

    return None


def _parse_candidate_idx(e_val: str, num_candidates: int) -> int | None:
    """Parse candidate index from e field: 'e1'->0, 'e2'->1, '1'->0, etc."""
    cleaned = e_val.replace("e", "").strip()
    try:
        idx = int(cleaned) - 1
        return idx if 0 <= idx < num_candidates else None
    except (ValueError, TypeError):
        return None
