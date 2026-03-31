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

    For each new fact, finds Jaccard 0.1-0.85 candidates from existing corpus,
    then sends ALL new facts + their candidates in ONE batched AI call.
    """
    existing_tokenized = [
        (sentence, version_uid, tokenize_fn(sentence))
        for sentence, version_uid in existing_facts
    ]

    # Build comparison blocks for all facts that have candidates
    fact_candidates: list[tuple[FcImportStagedFact, list[tuple[str, UUID]]]] = []

    for staged in staged_facts:
        staged_tokens = tokenize_fn(staged.display_sentence)
        candidates: list[tuple[str, UUID, float]] = []

        for sentence, version_uid, ex_tokens in existing_tokenized:
            score = jaccard_fn(staged_tokens, ex_tokens)
            if 0.1 <= score <= 0.85:
                candidates.append((sentence, version_uid, score))

        if not candidates:
            continue

        candidates.sort(key=lambda c: c[2], reverse=True)
        top = [(s, uid) for s, uid, _ in candidates[:8]]
        fact_candidates.append((staged, top))

    if not fact_candidates:
        return []

    # Batch into groups of ~4 new facts per AI call to keep token count reasonable
    results: list[dict] = []
    batch_size = 4
    for i in range(0, len(fact_candidates), batch_size):
        batch = fact_candidates[i : i + batch_size]
        batch_results = await _check_dcx_batch(batch, ai_key)
        results.extend(batch_results)

    return results


async def _check_dcx_batch(
    fact_candidates: list[tuple[FcImportStagedFact, list[tuple[str, UUID]]]],
    ai_key: str,
) -> list[dict]:
    """Send multiple N-facts with their candidates in one AI call."""
    system_prompt, user_template = load_skill("finddup")

    # Build v1-style comparison block with multiple N-facts
    lines: list[str] = []
    # Track which e-indices map to which candidates for each N-fact
    n_map: dict[int, tuple[FcImportStagedFact, list[tuple[str, UUID]]]] = {}
    e_counter = 1

    for n_idx, (staged, candidates) in enumerate(fact_candidates, start=1):
        n_map[n_idx] = (staged, candidates)
        lines.append(f"N{n_idx}: {staged.display_sentence}")
        for sentence, _ in candidates:
            lines.append(f"e{e_counter}: {sentence}")
            e_counter += 1

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
                "max_tokens": 4096,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()

    content = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(content)

    results: list[dict] = []
    # Parse results — find first D or C for each N-fact
    found_n: set[int] = set()

    for entry in data.get("r", data.get("results", [])):
        entry_type = str(entry.get("t", entry.get("type", "X"))).upper()
        if entry_type not in ("D", "C"):
            continue

        # Parse N-fact number from "n" field
        n_val = str(entry.get("n", ""))
        n_num = _parse_n_number(n_val)
        if n_num is None or n_num in found_n or n_num not in n_map:
            continue

        staged, candidates = n_map[n_num]

        # Parse candidate reference from "e" field
        e_val = str(entry.get("e", ""))
        # Calculate which candidate this e-index refers to
        # e-indices are global across all N-facts in the batch
        e_offset = 0
        for prev_n in range(1, n_num):
            if prev_n in n_map:
                e_offset += len(n_map[prev_n][1])

        e_idx = _parse_e_index(e_val)
        local_idx = (e_idx - e_offset) if e_idx is not None else None

        if local_idx is not None and 0 <= local_idx < len(candidates):
            version_uid = candidates[local_idx][1]
        elif candidates:
            version_uid = candidates[0][1]  # fallback to top candidate
        else:
            continue

        found_n.add(n_num)
        results.append({
            "staged_fact_uid": staged.staged_fact_uid,
            "type": "duplicate" if entry_type == "D" else "conflict",
            "version_uid": version_uid,
            "reason": entry.get("reason", "Detected by AI"),
        })

    return results


def _parse_n_number(n_val: str) -> int | None:
    """Parse N-fact number: 'N1'->1, '1'->1, 'N1'->1."""
    cleaned = n_val.replace("N", "").replace("n", "").strip()
    try:
        return int(cleaned)
    except (ValueError, TypeError):
        return None


def _parse_e_index(e_val: str) -> int | None:
    """Parse e-index: 'e1'->0, 'e2'->1, '3'->2, 'e3'->2."""
    cleaned = e_val.replace("e", "").strip()
    try:
        return int(cleaned) - 1  # 1-indexed to 0-indexed
    except (ValueError, TypeError):
        return None
