"""Jaccard similarity deduplication (ONE copy — regression: v1 I-ARCH-03)."""

from typing import Any


def tokenize(text: str) -> set[str]:
    """Split text into lowercase word tokens."""
    return set(text.lower().split())


def jaccard(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity between two token sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union


def deduplicate(
    new_facts: list[dict[str, Any]],
    existing_facts: list[dict[str, Any]],
    threshold: float = 0.85,
) -> list[dict[str, Any]]:
    """Compare new facts against existing corpus, flag duplicates.

    Each fact dict must have a 'sentence' key.
    Duplicates get 'duplicate_of' and 'similarity' keys added.
    """
    existing_tokens = [(f, tokenize(f.get("sentence", ""))) for f in existing_facts]
    results: list[dict[str, Any]] = []

    for new in new_facts:
        new_tokens = tokenize(new.get("sentence", ""))
        result = dict(new)
        for existing, ex_tokens in existing_tokens:
            score = jaccard(new_tokens, ex_tokens)
            if score >= threshold:
                result["duplicate_of"] = existing.get("fact_uid", existing.get("uid"))
                result["similarity"] = round(score, 4)
                break
        results.append(result)

    return results
