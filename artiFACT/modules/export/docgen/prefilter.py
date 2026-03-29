"""Two-pass AI affinity scoring: score all sections simultaneously, then assign."""

import json
from collections.abc import Awaitable, Callable
from typing import Any


async def score_facts_for_section(
    ai_call: Callable[[str], Awaitable[str]],
    facts: list[dict[str, Any]],
    section: dict[str, Any],
    all_sections: list[dict[str, Any]],
) -> dict[str, float]:
    """Score each fact's affinity for a given section using AI.

    Returns dict mapping fact index (str) to score (0.0-1.0).
    """
    if not facts:
        return {}

    fact_lines = "\n".join(f"  [{i}] {f['sentence']}" for i, f in enumerate(facts))
    section_list = "\n".join(f"  - {s['key']}: {s['title']}" for s in all_sections)

    prompt = (
        f"You are classifying facts into document sections.\n\n"
        f"TARGET SECTION: {section['key']} — {section['title']}\n"
        f"Section prompt: {section['prompt']}\n"
        f"Section guidance: {section.get('guidance', '')}\n\n"
        f"ALL SECTIONS in this document:\n{section_list}\n\n"
        f"FACTS:\n{fact_lines}\n\n"
        f"For each fact, rate its relevance to the TARGET SECTION on a scale of 0.0 to 1.0.\n"
        f"Consider that each fact should ideally go to exactly one section.\n"
        f"Return JSON: {{\"scores\": {{\"0\": 0.8, \"1\": 0.2, ...}}}}"
    )

    response = await ai_call(prompt)
    try:
        parsed = json.loads(response)
        return {str(k): float(v) for k, v in parsed.get("scores", {}).items()}
    except (json.JSONDecodeError, ValueError, AttributeError):
        return {}


def assign_facts_to_sections(
    affinity_scores: dict[str, dict[str, float]],
    facts: list[dict[str, Any]],
    threshold: float = 0.3,
) -> dict[str, list[dict[str, Any]]]:
    """Global assignment: each fact goes to highest-scoring section.

    Two-pass approach fixes v1's first-section-gets-first-pick bias:
    1. Collect all scores across all sections
    2. For each fact, assign to highest-scoring section (above threshold)
    """
    assignments: dict[str, list[dict[str, Any]]] = {key: [] for key in affinity_scores}

    for fact_idx in range(len(facts)):
        idx_str = str(fact_idx)
        best_section: str | None = None
        best_score = threshold

        for section_key, scores in affinity_scores.items():
            score = scores.get(idx_str, 0.0)
            if score > best_score:
                best_score = score
                best_section = section_key

        if best_section is not None:
            assignments[best_section].append(facts[fact_idx])

    return assignments
