"""Batch taxonomy classifier — integer-indexed, 8 facts per AI call."""

import json
from uuid import UUID

import httpx
import structlog
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.modules.import_pipeline.prompts import load_skill

log = structlog.get_logger()

AI_MODEL = "gpt-4.1"


async def build_taxonomy_index(
    db: AsyncSession,
    program_node_uid: UUID,
) -> tuple[str, dict[int, str]]:
    """Build integer-indexed taxonomy string and mapping dict.

    Uses a recursive CTE with tree-walk ordering (depth-first).
    Numbers nodes sequentially. Saves ~2,700 tokens per call vs UUIDs.
    """
    rows = (
        await db.execute(
            sa_text(
                "WITH RECURSIVE tree AS ("
                "  SELECT node_uid, title, node_depth, sort_order,"
                "         ARRAY[sort_order] AS path"
                "  FROM fc_node"
                "  WHERE node_uid = :root_uid AND is_archived = false"
                "  UNION ALL"
                "  SELECT n.node_uid, n.title, n.node_depth, n.sort_order,"
                "         t.path || n.sort_order"
                "  FROM fc_node n"
                "  JOIN tree t ON n.parent_node_uid = t.node_uid"
                "  WHERE n.is_archived = false"
                ") SELECT node_uid, title, node_depth FROM tree"
                " ORDER BY path"
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

    Uses nodesort skill. Response format: {"a":[[fact#,node#,confidence],...]}
    """
    system_prompt, user_template = load_skill("nodesort")

    numbered_facts = "\n".join(f"{i + 1}. {fact}" for i, fact in enumerate(facts))

    constraint_hint = ""
    if constraint_node_uids:
        reverse_map = {v: k for k, v in id_mapping.items()}
        # Collect the dropped nodes AND all their descendants from the taxonomy
        all_hint_ids: list[str] = []
        for uid_str in constraint_node_uids:
            parent_id = reverse_map.get(uid_str)
            if parent_id is not None:
                all_hint_ids.append(str(parent_id))
                # Find descendants: any node whose taxonomy line is more indented
                # and appears after the parent in the tree-walk order
                _collect_descendants(parent_id, id_mapping, taxonomy_text, all_hint_ids)
        if all_hint_ids:
            constraint_hint = (
                f"\nCONSTRAINT: STRONGLY prefer these nodes: {', '.join(all_hint_ids)}. "
                "Only go outside this set if nothing fits."
            )

    user_msg = user_template.format(
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
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                "max_tokens": 4096,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()

    content = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(content)

    # Parse compact format: {"a":[[fact#, node#], ...]} or {"a":[[fact#, node#, conf], ...]}
    assignments = data.get("a", [])

    results: list[dict] = []
    for i, fact in enumerate(facts):
        fact_num = i + 1
        matches = [a for a in assignments if len(a) >= 2 and a[0] == fact_num]

        if not matches:
            results.append({
                "sentence": fact,
                "suggested_node_uid": None,
                "node_confidence": None,
                "node_alternatives": [],
            })
            continue

        top = matches[0]
        node_id = top[1]
        top_uid = id_mapping.get(node_id) if node_id != 0 else None
        top_conf = top[2] if len(top) > 2 else 0.85

        results.append({
            "sentence": fact,
            "suggested_node_uid": top_uid,
            "node_confidence": top_conf,
            "node_alternatives": [],
        })

    return results


def _collect_descendants(
    parent_id: int,
    id_mapping: dict[int, str],
    taxonomy_text: str,
    result: list[str],
) -> None:
    """Find all descendant IDs of a parent node from the taxonomy text."""
    lines = taxonomy_text.split("\n")
    parent_indent = -1
    collecting = False
    for line in lines:
        # Parse "N  Title" format — count leading spaces after the number
        parts = line.split(" ", 1)
        if len(parts) < 2:
            continue
        try:
            node_id = int(parts[0])
        except ValueError:
            continue
        indent = len(parts[1]) - len(parts[1].lstrip())
        if node_id == parent_id:
            parent_indent = indent
            collecting = True
            continue
        if collecting:
            if indent > parent_indent:
                result.append(str(node_id))
            else:
                collecting = False


async def classify_all(
    facts: list[str],
    taxonomy_text: str,
    id_mapping: dict[int, str],
    ai_key: str,
    constraint_node_uids: list[str] | None = None,
    batch_size: int = 25,
) -> list[dict]:
    """Classify all facts in batches (default 25 = one call for most imports)."""
    results: list[dict] = []
    for i in range(0, len(facts), batch_size):
        batch = facts[i : i + batch_size]
        batch_results = await classify_batch(
            batch, taxonomy_text, id_mapping, ai_key, constraint_node_uids
        )
        results.extend(batch_results)
    return results
