"""AI-powered acronym expansion lookup (magic wand)."""

from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.ai_provider import AIProvider, record_ai_usage
from artiFACT.kernel.exceptions import NotFound
from artiFACT.kernel.models import FcAcronym, FcFact, FcFactVersion, FcUser

log = structlog.get_logger()

ACRONYM_LOOKUP_SYSTEM_PROMPT = (
    "You expand acronyms used in DoD acquisition and defense engineering. "
    "Given an acronym and facts from a defense program corpus that contain "
    "it, return ONLY the spelled-out expansion. No explanation, no "
    "punctuation, no quotes. If multiple expansions are common, return "
    "the most likely one given the corpus context. If you cannot determine "
    "the expansion, return \"UNKNOWN\"."
)

ACRONYM_LOOKUP_USER_TEMPLATE = (
    "ACRONYM: {acronym}\n\n"
    "CORPUS CONTEXT (facts containing this acronym):\n"
    "{context_facts}\n\n"
    "What does {acronym} stand for?"
)


async def _find_context_facts(
    db: AsyncSession,
    acronym_text: str,
    limit: int = 20,
) -> list[str]:
    """Find published facts containing the acronym."""
    tsquery = func.plainto_tsquery("english", acronym_text)
    result = await db.execute(
        select(FcFactVersion.display_sentence)
        .join(FcFact, FcFact.fact_uid == FcFactVersion.fact_uid)
        .where(
            FcFact.is_retired.is_(False),
            FcFactVersion.state.in_(["published", "signed"]),
            FcFact.current_published_version_uid == FcFactVersion.version_uid,
            FcFactVersion.search_vector.op("@@")(tsquery),
        )
        .limit(limit)
    )
    return [r.display_sentence for r in result.all()]


async def lookup_acronym_expansion(
    db: AsyncSession,
    acronym_uid: UUID,
    actor: FcUser,
) -> str:
    """Ask AI to expand an unresolved acronym using corpus context."""
    row = await db.get(FcAcronym, acronym_uid)
    if not row:
        raise NotFound("Acronym not found", code="ACRONYM_NOT_FOUND")

    context_facts = await _find_context_facts(db, row.acronym)

    if not context_facts:
        context_text = "(No corpus context available)"
    else:
        context_text = "\n".join(f"- {f}" for f in context_facts)

    messages = [
        {"role": "system", "content": ACRONYM_LOOKUP_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": ACRONYM_LOOKUP_USER_TEMPLATE.format(
                acronym=row.acronym,
                context_facts=context_text,
            ),
        },
    ]

    ai = AIProvider()
    content, usage = await ai.complete(
        db, actor.user_uid, messages, max_tokens=100, action="acronym_lookup",
    )

    expansion = content.strip().strip('"').strip("'")
    log.info("acronym.lookup", acronym=row.acronym, expansion=expansion)
    return expansion
