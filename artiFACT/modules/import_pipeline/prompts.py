"""AI prompt loader — reads skill .md files from skills/ directory.

Each skill file has ## system and ## user sections.
Python code calls load_skill('atomicfact') to get (system_prompt, user_template).
"""

from pathlib import Path

_SKILLS_DIR = Path(__file__).parent / "skills"
_cache: dict[str, tuple[str, str]] = {}


def load_skill(name: str) -> tuple[str, str]:
    """Load a skill file and return (system_prompt, user_template).

    Parses ## system and ## user sections from the markdown file.
    Results are cached after first load.
    """
    if name in _cache:
        return _cache[name]

    path = _SKILLS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Skill file not found: {path}")

    text = path.read_text(encoding="utf-8")
    system_prompt = _extract_section(text, "system")
    user_template = _extract_section(text, "user")

    _cache[name] = (system_prompt, user_template)
    return system_prompt, user_template


def _extract_section(text: str, heading: str) -> str:
    """Extract content between ## heading and the next ## or end of file."""
    marker = f"## {heading}"
    start = text.find(marker)
    if start == -1:
        raise ValueError(f"Section '## {heading}' not found in skill file")

    start = text.find("\n", start) + 1  # skip the ## line itself
    end = text.find("\n## ", start)
    if end == -1:
        end = len(text)

    return text[start:end].strip()


# Granularity -> max facts per chunk (not a prompt, just config)
GRANULARITY_MAP: dict[str, int] = {
    "brief": 10,
    "standard": 25,
    "exhaustive": 50,
}
