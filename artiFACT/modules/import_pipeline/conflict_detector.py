"""AI-powered duplicate + conflict detection (D/C/X) — uses finddup skill."""

import json
from collections.abc import Callable
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.ai_provider import AIProvider
from artiFACT.kernel.models import FcImportStagedFact
from artiFACT.modules.import_pipeline.prompts import load_skill

log = structlog.get_logger()


async def detect_conflicts(
    staged_facts: list[FcImportStagedFact],
    existing_facts: list[tuple[str, UUID]],
    db: AsyncSession,
    user_uid: UUID,
    jaccard_fn: Callable[[set[str], set[str]], float],
    tokenize_fn: Callable[[str], set[str]],
) -> list[dict]:
    """Detect duplicates AND contradictions using finddup skill.

    For each new fact, finds Jaccard 0.1-0.85 candidates, then sends
    all N-facts + a SHARED deduplicated candidate pool in one AI call.
    """
    existing_tokenized = [
        (sentence, version_uid, tokenize_fn(sentence))
        for sentence, version_uid in existing_facts
    ]

    # Build per-fact candidate lists
    fact_candidates: list[tuple[FcImportStagedFact, list[UUID]]] = []
    # Shared pool: version_uid -> (sentence, e_index)
    pool: dict[UUID, str] = {}
    pool_order: list[UUID] = []

    for staged in staged_facts:
        staged_tokens = tokenize_fn(staged.display_sentence)
        matches: list[tuple[UUID, float]] = []

        for sentence, version_uid, ex_tokens in existing_tokenized:
            score = jaccard_fn(staged_tokens, ex_tokens)
            if 0.1 <= score <= 0.85:
                matches.append((version_uid, score))
                if version_uid not in pool:
                    pool[version_uid] = sentence
                    pool_order.append(version_uid)

        if not matches:
            continue

        matches.sort(key=lambda m: m[1], reverse=True)
        top_uids = [uid for uid, _ in matches[:8]]
        fact_candidates.append((staged, top_uids))

    if not fact_candidates:
        return []

    # Batch into groups of ~6 N-facts per call
    results: list[dict] = []
    batch_size = 6
    for i in range(0, len(fact_candidates), batch_size):
        batch = fact_candidates[i : i + batch_size]
        # Collect only the pool entries needed for this batch
        batch_uids: set[UUID] = set()
        for _, uids in batch:
            batch_uids.update(uids)
        batch_pool = [(uid, pool[uid]) for uid in pool_order if uid in batch_uids]

        batch_results = await _check_dcx_batch(batch, batch_pool, db, user_uid)
        results.extend(batch_results)

    return results


async def _check_dcx_batch(
    fact_candidates: list[tuple[FcImportStagedFact, list[UUID]]],
    pool: list[tuple[UUID, str]],
    db: AsyncSession,
    user_uid: UUID,
) -> list[dict]:
    """Send N-facts with a shared deduplicated candidate pool."""
    system_prompt, user_template = load_skill("finddup")

    # Build shared e-list (deduplicated)
    e_map: dict[int, UUID] = {}  # 1-indexed e_num -> version_uid
    lines: list[str] = []
    for e_idx, (uid, sentence) in enumerate(pool, start=1):
        e_map[e_idx] = uid
        lines.append(f"e{e_idx}: {sentence}")

    # Add N-facts with their candidate e-numbers
    n_map: dict[int, FcImportStagedFact] = {}
    n_candidates: dict[int, list[int]] = {}

    for n_idx, (staged, candidate_uids) in enumerate(fact_candidates, start=1):
        n_map[n_idx] = staged
        # Find e-numbers for this fact's candidates
        e_nums = []
        for e_num, uid in e_map.items():
            if uid in candidate_uids:
                e_nums.append(e_num)
        n_candidates[n_idx] = e_nums
        candidate_refs = ",".join(f"e{n}" for n in e_nums)
        lines.append(f"N{n_idx}: {staged.display_sentence} [compare: {candidate_refs}]")

    user_msg = user_template.format(comparisons="\n".join(lines))

    ai = AIProvider()
    content = await ai.complete(
        db,
        user_uid,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        max_tokens=4096,
    )
    data = json.loads(content)

    results: list[dict] = []
    found_n: set[int] = set()

    for entry in data.get("r", data.get("results", [])):
        entry_type = str(entry.get("t", entry.get("type", "X"))).upper()
        if entry_type not in ("D", "C"):
            continue

        n_num = _parse_n_number(str(entry.get("n", "")))
        if n_num is None or n_num in found_n or n_num not in n_map:
            continue

        e_idx = _parse_e_index(str(entry.get("e", "")))
        version_uid = e_map.get(e_idx) if e_idx is not None else None

        if not version_uid:
            # Fallback: first candidate for this N-fact
            cands = n_candidates.get(n_num, [])
            version_uid = e_map.get(cands[0]) if cands else None

        if not version_uid:
            continue

        found_n.add(n_num)
        results.append({
            "staged_fact_uid": n_map[n_num].staged_fact_uid,
            "type": "duplicate" if entry_type == "D" else "conflict",
            "version_uid": version_uid,
            "reason": entry.get("reason", "Detected by AI"),
        })

    return results


def _parse_n_number(n_val: str) -> int | None:
    """Parse N-fact number: 'N1'->1, '1'->1."""
    cleaned = n_val.replace("N", "").replace("n", "").strip()
    try:
        return int(cleaned)
    except (ValueError, TypeError):
        return None


def _parse_e_index(e_val: str) -> int | None:
    """Parse e-index: 'e1'->1, 'e2'->2, '3'->3 (1-indexed)."""
    cleaned = str(e_val).replace("e", "").strip()
    try:
        return int(cleaned)
    except (ValueError, TypeError):
        return None
