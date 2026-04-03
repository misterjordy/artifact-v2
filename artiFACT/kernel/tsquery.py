"""Shared tsquery builder for full-text search."""

import re


def build_or_tsquery(terms: str) -> str:
    """Build an OR-joined tsquery string from space-separated terms.

    Deduplicates, strips non-alpha, joins with ' | '.
    Returns empty string if no valid terms.
    """
    words = re.findall(r"[A-Za-z0-9]+", terms.lower())
    seen: set[str] = set()
    unique: list[str] = []
    for w in words:
        if len(w) > 1 and w not in seen:
            seen.add(w)
            unique.append(w)
    return " | ".join(unique) if unique else ""
