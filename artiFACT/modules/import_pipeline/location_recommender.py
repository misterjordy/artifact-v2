"""AI-powered node placement recommendation (ONE copy — regression: v1 I-LOW-04)."""

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.crypto import decrypt
from artiFACT.kernel.models import FcNode, FcUser, FcUserAiKey
from artiFACT.modules.ai_chat.service import _call_provider

RECOMMEND_PROMPT = """You are a taxonomy classification engine. Given a list of factual statements
and a taxonomy tree, recommend the best node for each statement.

Return a JSON object with a "recommendations" array. Each item has:
- "sentence": the original statement
- "recommended_node_uid": the UID of the best-fit node
- "reasoning": brief explanation of why this node fits

Consider the node titles and hierarchy when making recommendations."""


async def recommend_locations(
    db: AsyncSession,
    sentences: list[str],
    program_node_uid: UUID,
    actor: FcUser,
) -> list[dict]:
    """Use AI to recommend node placements for extracted facts."""
    nodes_result = await db.execute(
        select(FcNode).where(FcNode.is_archived.is_(False)).order_by(FcNode.node_depth)
    )
    nodes = nodes_result.scalars().all()
    taxonomy = "\n".join(f"{'  ' * n.node_depth}{n.title} (uid: {n.node_uid})" for n in nodes)

    ai_key_result = await db.execute(
        select(FcUserAiKey).where(FcUserAiKey.user_uid == actor.user_uid)
    )
    ai_key = ai_key_result.scalar_one_or_none()
    if not ai_key:
        return [
            {
                "sentence": s,
                "recommended_node_uid": str(program_node_uid),
                "reasoning": "No AI key configured",
            }
            for s in sentences
        ]

    plaintext_key = decrypt(ai_key.encrypted_key)
    messages = [
        {"role": "system", "content": RECOMMEND_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "sentences": sentences,
                    "taxonomy": taxonomy,
                }
            ),
        },
    ]

    response_text = await _call_provider(ai_key, plaintext_key, messages, stream=False)

    try:
        data = json.loads(response_text)
        return data.get("recommendations", [])
    except (json.JSONDecodeError, TypeError):
        return [
            {
                "sentence": s,
                "recommended_node_uid": str(program_node_uid),
                "reasoning": "AI response parsing failed",
            }
            for s in sentences
        ]
