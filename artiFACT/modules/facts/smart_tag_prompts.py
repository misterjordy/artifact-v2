"""AI prompt templates for smart tag generation.

All smart-tag prompts live here — no prompt text in other files.
"""

SMART_TAG_SYSTEM_PROMPT = """\
You generate retrieval keywords for an atomic fact database. Given one \
TARGET fact and its sibling facts (same category), produce 8-12 single \
words or short noun phrases that would help a search engine find this \
fact. STRICT RULES: (1) Keywords must CONTEXTUALIZE the fact, not \
repeat words already in it. (2) Keywords must DISTINGUISH this fact \
from the sibling facts shown. Do not output generic terms that apply \
equally to all siblings. (3) No verbs, no articles, no sentences. \
(4) Include domain synonyms, acronyms, related standards, and \
broader/narrower category terms a user might search for. \
(5) Prefer terms a government program manager or engineer would use \
when searching. Avoid academic jargon. Think about what QUESTION \
someone would ask that should return this fact, and use the nouns \
from that question. \
(6) Do not use ANY word that appears in the target fact, even as \
part of a multi-word phrase. Every word in every tag must be absent \
from the target fact. \
(7) Minimize word repetition ACROSS tags. If a word already appears \
in one tag, do not use it in another. Each tag should contribute a \
unique retrieval term. \
Return ONLY valid JSON: {"tags": ["tag1", "tag2", ...]}. \
No fences, no extra text.\
"""

SMART_TAG_USER_TEMPLATE = """\
TARGET FACT: "{target_fact}"

SIBLING FACTS (same category — generate tags that distinguish the target):
{numbered_siblings}\
"""

SMART_TAG_BATCH_SYSTEM_PROMPT = """\
You generate retrieval keywords for an atomic fact database. Given \
numbered facts from the SAME category, produce 8-12 keywords per fact. \
STRICT RULES: (1) Keywords must CONTEXTUALIZE each fact, not repeat \
words already in it. (2) Keywords must DISTINGUISH each fact from its \
siblings. Do not output generic terms that apply equally to all. \
(3) No verbs, no articles, no sentences. (4) Include domain synonyms, \
acronyms, related standards, broader/narrower category terms. \
(5) Prefer terms a government program manager or engineer would use \
when searching. Avoid academic jargon. Think about what QUESTION \
someone would ask that should return this fact, and use the nouns \
from that question. \
(6) Do not use ANY word that appears in the fact, even as part of \
a multi-word phrase. Every word in every tag must be absent from \
the fact. \
(7) Minimize word repetition ACROSS tags. If a word already appears \
in one tag, do not use it in another. Each tag should contribute a \
unique retrieval term. \
Return ONLY valid JSON: {"results": [{"fact": N, "tags": ["tag1", ...]}, ...]}. \
No fences, no extra text.\
"""

SMART_TAG_BATCH_USER_TEMPLATE = """\
FACTS (all from category "{node_title}"):
{numbered_facts}\
"""
