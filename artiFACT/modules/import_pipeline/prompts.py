"""AI prompt templates for the import pipeline.

All prompts are defined here — no prompt text in other files.
"""

EXTRACTOR_SYSTEM_PROMPT = (
    "You extract atomic facts from government "
    "program documents. STRICT RULES: (1) ATOMIC = one fact per line. Each "
    "fact states exactly ONE subject-verb-object assertion. (2) SPLIT "
    "AGGRESSIVELY: If a sentence lists multiple values, quantities, items, "
    "or attributes, split each into its own fact. Example: \"The hull has 22 "
    "transverse bulkheads, 6 longitudinal bulkheads, and 112 watertight "
    'compartments" \u2192 THREE facts: "The hull has 22 transverse bulkheads" / '
    '"The hull has 6 longitudinal bulkheads" / "The hull has 112 watertight '
    'compartments". (3) No compound sentences. No semicolons. No commas '
    "joining separate assertions. No \"and\" connecting distinct facts. (4) Be "
    "specific \u2014 include numbers, names, dates, standards, thresholds exactly "
    "as written. (5) Do not infer, combine, or rephrase beyond minimal "
    "cleanup. (6) Omit filler, headers, labels, and navigation text \u2014 only "
    'factual content. Return ONLY valid JSON: {"facts": ["fact 1", "fact 2", ...]}'
)

EXTRACTOR_USER_TEMPLATE = (
    "Extract up to {max_facts} atomic facts from this document section.\n\n{chunk_text}"
)

CLASSIFIER_SYSTEM_PROMPT = (
    "Taxonomy classifier for a DoD acquisition "
    "fact corpus. Given numbered facts and an indented taxonomy tree (numeric "
    "id + title), return the 3 best-matching node ids for EACH fact. Return "
    'ONLY valid JSON: {"results":[{"fact":N,"nodes":[{"id":M,"confidence":0.92,'
    '"reason":"one sentence"},{"id":M,"confidence":0.78,"reason":"one sentence"},'
    '{"id":M,"confidence":0.65,"reason":"one sentence"}]},...]}. Top 3 nodes '
    "per fact ranked by relevance. No fences, no extra text."
)

CLASSIFIER_USER_TEMPLATE = """FACTS:
{numbered_facts}

TAXONOMY:
{taxonomy_text}
{constraint_hint}"""

CONFLICT_SYSTEM_PROMPT = (
    "You detect contradictions between facts in a "
    "DoD acquisition corpus. A contradiction means the new fact and an existing "
    "fact cannot both be true simultaneously \u2014 they assert incompatible values, "
    "dates, quantities, or states. Similar wording alone is NOT a contradiction. "
    'Return ONLY valid JSON: {"results":[{"existing":N,"contradicts":true, '
    '"reason":"explanation"},...]}. Only include entries where contradicts=true. '
    "No fences, no extra text."
)

CONFLICT_USER_TEMPLATE = """NEW FACT: "{new_fact}"

EXISTING FACTS:
{numbered_existing}

Do any of these existing facts contradict the new fact?"""

# Granularity -> max facts per chunk
GRANULARITY_MAP: dict[str, int] = {
    "brief": 10,
    "standard": 25,
    "exhaustive": 50,
}
