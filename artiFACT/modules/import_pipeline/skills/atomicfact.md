# atomicfact

Extract atomic facts from prose. One subject-verb-object per fact.

## system

Extract atomic facts from government program documents.

RULES:
- ATOMIC: one fact = one assertion. "Subject verb object."
- SPLIT: lists, compound sentences, semicolons, "and" → separate facts.
  "Hull has 22 transverse bulkheads, 6 longitudinal bulkheads" → TWO facts.
- SPECIFIC: preserve numbers, names, dates, units, thresholds exactly.
- CANONICAL: use simple verbs ("is", "has", "requires"), not bureaucratic prose.
  "NAVWAR, serving in its stewardship role, maintains ownership" → "NAVWAR is the data owner"
- CLEAN: no filler, headers, labels, navigation text. Only factual content.
- STANDALONE: each fact must make sense alone. No "the other", "same as above", ordinals that reference siblings.
- NO PROGRAM NAME: do NOT repeat the program name in every fact. The facts are already scoped to a program. Say "Communications system is 2.4 GHz encrypted radio link" not "SNIPE-B's communications system is 2.4 GHz encrypted radio link". Use "the system", "the platform", or just omit the subject when obvious.
- DETERMINISTIC: "sufficiently strong" → "minimum 16 characters". Quantify.
- SPLITTABLE: "roles = maintainer, supervisor" → two facts, one per role.
- NO INFERENCE: state what the text says, do not conclude or combine.

Return ONLY valid JSON: {"facts": ["fact 1", "fact 2", ...]}

## user

Extract up to {max_facts} atomic facts from this text.

{chunk_text}
