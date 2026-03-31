"""Batch taxonomy classifier — integer-indexed, 8 facts per AI call."""

import json
from uuid import UUID

import httpx
import structlog
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.modules.import_pipeline.prompts import (
    CLASSIFIER_SYSTEM_PROMPT,
    CLASSIFIER_USER_TEMPLATE,
)

log = structlog.get_logger()

AI_MODEL = "gpt-4.1"


async def build_taxonomy_index(
    db: AsyncSession,
    program_node_uid: UUID,
) -> tuple[str, dict[int, str]]:
    """Build integer-indexed taxonomy string and mapping dict.

    Uses a recursive CTE to get all descendant nodes under the program node.
    Numbers them sequentially. Saves ~2,700 tokens per classifier call vs UUIDs.
    """
    rows = (
        await db.execute(
            sa_text(
                "WITH RECURSIVE tree AS ("
                "  SELECT node_uid, title, node_depth, sort_order"
                "  FROM fc_node"
                "  WHERE node_uid = :root_uid AND is_archived = false"
                "  UNION ALL"
                "  SELECT n.node_uid, n.title, n.node_depth, n.sort_order"
                "  FROM fc_node n"
                "  JOIN tree t ON n.parent_node_uid = t.node_uid"
                "  WHERE n.is_archived = false"
                ") SELECT node_uid, title, node_depth FROM tree"
                " ORDER BY node_depth, sort_order"
            ),
            {"root_uid": str(program_node_uid)},
        )
    ).fetchall()

    id_mapping: dict[int, str] = {}
    lines: list[str] = []
    for idx, row in enumerate(rows, start=1):
        node_uid_str = str(row[0])
        title = row[1]
        depth = row[2]
        id_mapping[idx] = node_uid_str
        indent = "  " * depth
        lines.append(f"{idx} {indent}{title}")

    taxonomy_text = "\n".join(lines)
    return taxonomy_text, id_mapping


async def classify_batch(
    facts: list[str],
    taxonomy_text: str,
    id_mapping: dict[int, str],
    ai_key: str,
    constraint_node_uids: list[str] | None = None,
) -> list[dict]:
    """Classify up to 8 facts at once against the taxonomy.

    Sends one AI call with all facts + taxonomy. Maps integer IDs back to UUIDs.
    """
    numbered_facts = "\n".join(f"{i + 1}. {fact}" for i, fact in enumerate(facts))

    constraint_hint = ""
    if constraint_node_uids:
        # Build hint from constraint nodes that appear in the mapping
        reverse_map = {v: k for k, v in id_mapping.items()}
        hint_parts: list[str] = []
        for uid_str in constraint_node_uids:
            int_id = reverse_map.get(uid_str)
            if int_id is not None:
                hint_parts.append(str(int_id))
        if hint_parts:
            constraint_hint = (
                f"\nPriority nodes (prefer these if relevant): {', '.join(hint_parts)}"
            )

    user_msg = CLASSIFIER_USER_TEMPLATE.format(
        numbered_facts=numbered_facts,
        taxonomy_text=taxonomy_text,
        constraint_hint=constraint_hint,
    )

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {ai_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": AI_MODEL,
                "messages": [
                    {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "max_tokens": 4096,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()

    content = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(content)

    results: list[dict] = []
    for i, fact in enumerate(facts):
        fact_num = i + 1
        fact_result = _find_fact_result(data.get("results", []), fact_num)

        if not fact_result or not fact_result.get("nodes"):
            results.append({
                "sentence": fact,
                "suggested_node_uid": None,
                "node_confidence": None,
                "node_alternatives": [],
            })
            continue

        nodes = fact_result["nodes"]
        top = nodes[0]
        top_uid = id_mapping.get(top["id"])

        alternatives = []
        for alt in nodes[1:3]:
            alt_uid = id_mapping.get(alt["id"])
            if alt_uid:
                alternatives.append({
                    "node_uid": alt_uid,
                    "confidence": alt.get("confidence", 0),
                    "reason": alt.get("reason", ""),
                })

        results.append({
            "sentence": fact,
            "suggested_node_uid": top_uid,
            "node_confidence": top.get("confidence", 0),
            "node_alternatives": alternatives,
        })

    return results


def _find_fact_result(results: list[dict], fact_num: int) -> dict | None:
    """Find the result entry for a given fact number."""
    for r in results:
        if r.get("fact") == fact_num:
            return r
    return None


async def classify_all(
    facts: list[str],
    taxonomy_text: str,
    id_mapping: dict[int, str],
    ai_key: str,
    constraint_node_uids: list[str] | None = None,
    batch_size: int = 8,
) -> list[dict]:
    """Classify all facts in batches of batch_size."""
    results: list[dict] = []
    for i in range(0, len(facts), batch_size):
        batch = facts[i : i + batch_size]
        batch_results = await classify_batch(
            batch, taxonomy_text, id_mapping, ai_key, constraint_node_uids
        )
        results.extend(batch_results)
    return results
