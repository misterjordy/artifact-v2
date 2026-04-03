"""AI-powered program description generator.

BM25 overgathers descriptive facts from all subnodes, then synthesizes
a dense 2-4 sentence program description via LLM.
"""

from uuid import UUID

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.ai_provider import AIProvider, record_ai_usage
from artiFACT.kernel.exceptions import Conflict
from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcUser
from artiFACT.modules.facts.smart_tags import get_descendant_node_uids

log = structlog.get_logger()

MAX_FACTS_TO_SEND = 200

PROGRAM_DESCRIPTION_SYSTEM_PROMPT = """\
You write concise program descriptions for DoD acquisition systems. \
Given a program name and its corpus of atomic facts, write a dense \
2-4 sentence description that covers: what the system IS, what it \
DOES, who it's FOR, and how it's BUILT (if relevant). STRICT RULES: \
(1) Maximum 80 words. Be dense and specific — every word must earn \
its place. (2) Use plain language a program manager would use. No \
jargon for jargon's sake. (3) Include specific details from the \
facts: names, numbers, standards, classifications. Do not be vague. \
(4) Do not start with "The [program name] program..." — vary your \
opening. (5) Do not list facts — synthesize them into flowing prose. \
(6) If the facts mention classification level, hosting environment, \
or acquisition pathway, include those. \
Return ONLY the description paragraph. No headers, no bullet points, \
no markdown.\
"""

PROGRAM_DESCRIPTION_USER_TEMPLATE = """\
PROGRAM: {program_name}

The following {fact_count} facts describe this program. Synthesize \
them into a 2-4 sentence program description (max 80 words):

{facts_text}\
"""


async def _load_descendant_facts(
    db: AsyncSession,
    descendant_uids: list[UUID],
) -> list[tuple[str, list[str]]]:
    """Load all published/signed fact sentences + smart_tags from descendants."""
    stmt = (
        select(
            FcFactVersion.display_sentence,
            FcFactVersion.smart_tags,
        )
        .join(FcFact, FcFact.fact_uid == FcFactVersion.fact_uid)
        .where(
            FcFact.is_retired.is_(False),
            FcFactVersion.state.in_(["published", "signed"]),
            FcFact.node_uid.in_(descendant_uids),
            FcFact.current_published_version_uid == FcFactVersion.version_uid,
        )
        .order_by(FcFactVersion.created_at)
    )
    result = await db.execute(stmt)
    return list(result.all())


async def _bm25_select_descriptive(
    db: AsyncSession,
    descendant_uids: list[UUID],
    limit: int = MAX_FACTS_TO_SEND,
) -> list[tuple[str, list[str]]]:
    """Use BM25 with descriptive query terms to select top facts."""
    descriptive_terms = (
        "purpose | mission | capability | description | overview "
        "| system | platform | designation | type | objective | function"
    )
    tsquery = func.to_tsquery("english", descriptive_terms)
    stmt = (
        select(
            FcFactVersion.display_sentence,
            FcFactVersion.smart_tags,
            func.ts_rank(FcFactVersion.search_vector, tsquery).label("score"),
        )
        .join(FcFact, FcFact.fact_uid == FcFactVersion.fact_uid)
        .where(
            FcFact.is_retired.is_(False),
            FcFactVersion.state.in_(["published", "signed"]),
            FcFact.node_uid.in_(descendant_uids),
            FcFact.current_published_version_uid == FcFactVersion.version_uid,
        )
        .order_by(text("score DESC"))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def generate_program_description(
    db: AsyncSession,
    node_uid: UUID,
    actor: FcUser,
) -> tuple[str, int]:
    """Generate a program description from its corpus of facts.

    Returns (description, total_tokens_used).
    """
    node = await db.get(FcNode, node_uid)
    if not node or not node.is_program:
        raise Conflict("Node is not a program")

    descendant_uids = await get_descendant_node_uids(db, node_uid)
    all_facts = await _load_descendant_facts(db, descendant_uids)

    if len(all_facts) > MAX_FACTS_TO_SEND:
        facts_to_send = await _bm25_select_descriptive(db, descendant_uids)
    else:
        facts_to_send = all_facts

    fact_lines = [
        f"{i}. {row[0]}" for i, row in enumerate(facts_to_send, 1)
    ]
    facts_text = "\n".join(fact_lines)

    messages = [
        {"role": "system", "content": PROGRAM_DESCRIPTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": PROGRAM_DESCRIPTION_USER_TEMPLATE.format(
                program_name=node.title,
                fact_count=len(facts_to_send),
                facts_text=facts_text,
            ),
        },
    ]

    ai = AIProvider()
    content, usage = await ai.complete(
        db,
        actor.user_uid,
        messages,
        max_tokens=300,
        action="program_description",
    )

    description = content.strip()
    log.info(
        "program_description.generated",
        node_uid=str(node_uid),
        fact_count=len(facts_to_send),
        tokens=usage.total_tokens,
    )
    return description, usage.total_tokens


async def estimate_description_tokens(
    db: AsyncSession,
    node_uid: UUID,
) -> dict[str, int]:
    """Estimate token cost for generating a program description."""
    descendant_uids = await get_descendant_node_uids(db, node_uid)

    fact_count_result = await db.execute(
        select(func.count())
        .select_from(FcFactVersion)
        .join(FcFact, FcFact.fact_uid == FcFactVersion.fact_uid)
        .where(
            FcFact.is_retired.is_(False),
            FcFactVersion.state.in_(["published", "signed"]),
            FcFact.node_uid.in_(descendant_uids),
            FcFact.current_published_version_uid == FcFactVersion.version_uid,
        )
    )
    fact_count = fact_count_result.scalar() or 0

    facts_sent = min(fact_count, MAX_FACTS_TO_SEND)
    estimated_input = 200 + (facts_sent * 15)
    estimated_output = 100
    estimated_total = estimated_input + estimated_output

    return {
        "fact_count": fact_count,
        "facts_sent": facts_sent,
        "estimated_input_tokens": estimated_input,
        "estimated_output_tokens": estimated_output,
        "estimated_total_tokens": estimated_total,
    }
