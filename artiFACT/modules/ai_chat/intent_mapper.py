"""Static intent archetype mapper for query expansion.

Maps natural language question patterns to retrieval keyword buckets.
Zero LLM cost — pure pattern matching. The keywords are injected
into the BM25 query to improve recall on vague questions.
"""

import re

INTENT_MAP: dict[str, dict] = {
    "describe": {
        "patterns": [
            r"\bwhat is\b", r"\bwhat does\b", r"\bwhat are\b",
            r"\btell me about\b", r"\bdescribe\b", r"\boverview\b",
            r"\bsummary\b", r"\bsummarize\b", r"\bexplain\b",
            r"\bwhat('s| is) this\b", r"\bwhat('s| is) it\b",
            r"\bintroduc", r"\bpurpose\b",
        ],
        "tags": [
            "description", "purpose", "capability", "mission",
            "designation", "platform", "type", "objective",
        ],
    },
    "cost": {
        "patterns": [
            r"\bhow much\b", r"\bcost\b", r"\bprice\b", r"\bbudget\b",
            r"\bfunding\b", r"\bafford\b", r"\bexpens", r"\bsustainment\b",
            r"\blicense\b", r"\bsubscription\b",
        ],
        "tags": [
            "cost", "funding", "budget", "sustainment", "license",
            "subscription", "annual", "pricing",
        ],
    },
    "security": {
        "patterns": [
            r"\bsecur", r"\bauth\b", r"\bencrypt", r"\bprotect\b",
            r"\bcompli", r"\bato\b", r"\brmf\b", r"\bcui\b",
            r"\bzero trust\b", r"\bvulnerab",
        ],
        "tags": [
            "encryption", "authentication", "authorization", "compliance",
            "boundary", "CUI", "RMF", "zero trust", "ATO",
        ],
    },
    "architecture": {
        "patterns": [
            r"\bhow does\b", r"\barchitect", r"\bstack\b",
            r"\binfrastructur", r"\bbuilt with\b", r"\btech stack\b",
            r"\bdesign\b", r"\btechnolog",
        ],
        "tags": [
            "architecture", "database", "framework", "deployment",
            "container", "hosting", "infrastructure", "stack",
        ],
    },
    "people": {
        "patterns": [
            r"\bwho\b", r"\bteam\b", r"\broles?\b", r"\bresponsib",
            r"\bmanager\b", r"\busers?\b", r"\bstakeholder",
        ],
        "tags": [
            "role", "user", "manager", "approver", "signatory",
            "personnel", "stakeholder", "responsibility",
        ],
    },
    "data": {
        "patterns": [
            r"\bdata\b", r"\bexport\b", r"\bfeed\b", r"\bsync\b",
            r"\bformat\b", r"\bintegrat", r"\badvana\b", r"\bjupiter\b",
            r"\bapi\b",
        ],
        "tags": [
            "export", "sync", "format", "API", "feed", "integration",
            "JSON", "Advana", "delta",
        ],
    },
    "process": {
        "patterns": [
            r"\bhow do i\b", r"\bworkflow\b", r"\bsteps?\b",
            r"\bprocess\b", r"\bapprov", r"\bsign\b", r"\bqueue\b",
            r"\bpropose\b", r"\bsubmit\b",
        ],
        "tags": [
            "workflow", "approval", "signature", "state", "transition",
            "queue", "proposal", "review",
        ],
    },
    "import": {
        "patterns": [
            r"\bimport\b", r"\bupload\b", r"\bextract\b", r"\bingest\b",
            r"\bpaste\b", r"\bdocument upload\b",
        ],
        "tags": [
            "import", "upload", "extraction", "staging", "pipeline",
            "classification", "document",
        ],
    },
}

FALLBACK_TAGS: list[str] = [
    "description", "purpose", "capability", "architecture", "overview",
]


def detect_intent(query: str) -> tuple[str, list[str]]:
    """Return (intent_name, expansion_tags) for a query.

    Scans INTENT_MAP patterns in order. First match wins.
    Returns ("fallback", FALLBACK_TAGS) if nothing matches.
    """
    normalized = query.lower().strip()
    for intent_name, config in INTENT_MAP.items():
        for pattern in config["patterns"]:
            if re.search(pattern, normalized):
                return intent_name, config["tags"]
    return "fallback", list(FALLBACK_TAGS)


def expand_query(query: str) -> str:
    """Expand query with intent tags for BM25 search.

    Returns the original query + space-separated intent tags.
    """
    _, tags = detect_intent(query)
    return f"{query} {' '.join(tags)}"


def enrich_query_with_context(
    query: str,
    chat_state: dict | None,
    current_node_name: str | None,
) -> str:
    """Add conversational context to short/ambiguous queries.

    - If query contains pronouns and current_node_name exists: append node name
    - Append mentioned_entities from chat history (up to 5)
    """
    enriched = query
    if current_node_name and re.search(r"\b(it|this|that|these|those)\b", query.lower()):
        enriched = f"{enriched} {current_node_name}"
    if chat_state and chat_state.get("mentioned_entities"):
        entities = chat_state["mentioned_entities"][:5]
        enriched = f"{enriched} {' '.join(entities)}"
    return enriched
