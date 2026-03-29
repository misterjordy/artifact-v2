"""Layer 1: Injection detection via regex + Unicode NFKC + confusable mapping."""

import re
import unicodedata
from dataclasses import dataclass, field

# Confusable character mappings (Cyrillic homoglyphs -> Latin)
CONFUSABLE_MAP: dict[str, str] = {
    "\u0430": "a",  # Cyrillic а → Latin a
    "\u0435": "e",  # Cyrillic е → Latin e
    "\u043e": "o",  # Cyrillic о → Latin o
    "\u0440": "p",  # Cyrillic р → Latin p
    "\u0441": "c",  # Cyrillic с → Latin c
    "\u0443": "y",  # Cyrillic у → Latin y
    "\u0445": "x",  # Cyrillic х → Latin x
    "\u0456": "i",  # Cyrillic і → Latin i
    "\u0458": "j",  # Cyrillic ј → Latin j
    "\u04bb": "h",  # Cyrillic һ → Latin h
    "\u0410": "A",  # Cyrillic А → Latin A
    "\u0412": "B",  # Cyrillic В → Latin B
    "\u0415": "E",  # Cyrillic Е → Latin E
    "\u041a": "K",  # Cyrillic К → Latin K
    "\u041c": "M",  # Cyrillic М → Latin M
    "\u041d": "H",  # Cyrillic Н → Latin H
    "\u041e": "O",  # Cyrillic О → Latin O
    "\u0420": "P",  # Cyrillic Р → Latin P
    "\u0421": "C",  # Cyrillic С → Latin C
    "\u0422": "T",  # Cyrillic Т → Latin T
    "\u0425": "X",  # Cyrillic Х → Latin X
}


@dataclass
class InputCheckResult:
    clean: bool
    flags: list[str] = field(default_factory=list)
    normalized: str = ""


# Injection patterns to detect
_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "system_override",
        re.compile(
            r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|rules?|prompts?)",
            re.IGNORECASE,
        ),
    ),
    (
        "role_injection",
        re.compile(
            r"(you\s+are\s+now|act\s+as|pretend\s+(to\s+be|you\s+are)|new\s+instructions?)",
            re.IGNORECASE,
        ),
    ),
    (
        "data_exfil",
        re.compile(
            r"(list|dump|show|give|output|repeat|print)\s+(all|every|each)\s+(facts?|data|content|information)",
            re.IGNORECASE,
        ),
    ),
    (
        "prompt_leak",
        re.compile(
            r"(show|reveal|display|output|repeat)\s+(your\s+)?(system\s+)?(prompt|instructions?|rules?)",
            re.IGNORECASE,
        ),
    ),
    (
        "encoding_bypass",
        re.compile(
            r"(base64|hex|rot13|reverse|encode|decode)\s+(the\s+)?(output|response|answer)",
            re.IGNORECASE,
        ),
    ),
]


def map_confusables(text: str) -> str:
    """Replace known confusable characters with their ASCII equivalents."""
    return "".join(CONFUSABLE_MAP.get(ch, ch) for ch in text)


def check_input(text: str) -> InputCheckResult:
    """Normalize Unicode and check for injection patterns.

    Flags but does NOT block — Layer 2 (system prompt) handles defense.
    """
    normalized = unicodedata.normalize("NFKC", text)
    normalized = map_confusables(normalized)

    flags: list[str] = []
    for name, pattern in _INJECTION_PATTERNS:
        if pattern.search(normalized):
            flags.append(name)

    return InputCheckResult(
        clean=len(flags) == 0,
        flags=flags,
        normalized=normalized,
    )
