"""Token-counted system prompt construction (fixes v1 A-SEC-01: no byte truncation)."""

import tiktoken

from artiFACT.modules.ai_chat.safety.system_hardening import SYSTEM_INSTRUCTIONS

_enc = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens using tiktoken cl100k_base encoding."""
    return len(_enc.encode(text))


def build_system_prompt(
    facts: list[str],
    max_tokens: int = 6000,
) -> tuple[str, int, int]:
    """Build system prompt with proper token counting, never byte truncation.

    Returns (prompt_text, facts_loaded, facts_total).
    """
    header = SYSTEM_INSTRUCTIONS
    header_tokens = count_tokens(header)
    token_budget = max_tokens - header_tokens - 200  # headroom

    included: list[str] = []
    used_tokens = 0
    for fact in facts:
        fact_line = f"- {fact}"
        tokens = count_tokens(fact_line)
        if used_tokens + tokens > token_budget:
            break
        included.append(fact_line)
        used_tokens += tokens

    facts_section = f"\n\nFACTS ({len(included)} loaded of {len(facts)} total):\n"
    prompt = header + facts_section + "\n".join(included)
    return prompt, len(included), len(facts)
