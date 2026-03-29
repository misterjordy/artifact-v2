"""AI text synthesis per section — streaming via AI provider."""

from collections.abc import Awaitable, Callable
from typing import Any


async def synthesize_section(
    ai_call: Callable[[str], Awaitable[str]],
    facts: list[dict[str, Any]],
    section_prompt: str,
    section_title: str,
) -> str:
    """Synthesize narrative text for a section from assigned facts.

    Args:
        ai_call: async callable that takes a prompt string and returns text.
        facts: list of fact dicts assigned to this section.
        section_prompt: the template's prompt describing what this section should contain.
        section_title: human-readable section title.

    Returns:
        Synthesized text for the section.
    """
    if not facts:
        return "No facts were assigned to this section."

    fact_lines = "\n".join(f"- {f['sentence']}" for f in facts)

    prompt = (
        f'You are writing section "{section_title}" of a formal document.\n\n'
        f"SECTION GUIDANCE: {section_prompt}\n\n"
        f"SOURCE FACTS:\n{fact_lines}\n\n"
        f"Write a coherent, professional narrative that synthesizes these facts into a "
        f"well-structured section. Use formal technical writing style. "
        f"Do not invent information beyond what the facts state. "
        f"Do not include section headers — just the body text."
    )

    return await ai_call(prompt)
