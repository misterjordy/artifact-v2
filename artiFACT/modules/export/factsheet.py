"""Flat fact export in TXT, JSON, NDJSON, CSV formats."""

import csv
import io
import json
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Forbidden
from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcUser
from artiFACT.kernel.permissions.resolver import can


async def _expand_nodes(db: AsyncSession, node_uids: list) -> list:
    """Expand node UIDs to include all descendants."""
    all_uids = set(node_uids)
    for uid in node_uids:
        descendants = await _get_descendants(db, uid)
        all_uids.update(descendants)
    return list(all_uids)


async def _get_descendants(db: AsyncSession, node_uid: object) -> list:
    """Get all descendant node UIDs recursively."""
    cte = (
        select(FcNode.node_uid)
        .where(FcNode.parent_node_uid == node_uid, FcNode.is_archived.is_(False))
        .cte(name="desc", recursive=True)
    )
    cte = cte.union_all(
        select(FcNode.node_uid)
        .join(cte, FcNode.parent_node_uid == cte.c.node_uid)
        .where(FcNode.is_archived.is_(False))
    )
    result = await db.execute(select(cte.c.node_uid))
    return [row[0] for row in result.all()]


async def load_facts_for_export(
    db: AsyncSession, node_uids: list, state_filter: list[str]
) -> list[dict]:
    """Load facts with their current published version, filtered by node and state."""
    expanded = await _expand_nodes(db, node_uids)
    stmt = (
        select(FcFact, FcFactVersion, FcNode)
        .join(FcFactVersion, FcFact.current_published_version_uid == FcFactVersion.version_uid)
        .join(FcNode, FcFact.node_uid == FcNode.node_uid)
        .where(
            FcFact.node_uid.in_(expanded),
            FcFact.is_retired.is_(False),
            FcFactVersion.state.in_(state_filter),
        )
        .order_by(FcNode.title, FcFact.created_at)
    )
    result = await db.execute(stmt)
    rows = result.all()

    facts = []
    for idx, (fact, version, node) in enumerate(rows, 1):
        facts.append(
            {
                "seq": idx,
                "node": node.title,
                "sentence": version.display_sentence,
                "state": version.state,
                "classification": version.classification or "UNCLASSIFIED",
                "effective_date": version.effective_date,
                "last_verified": version.last_verified_date,
                "tags": version.metadata_tags or [],
            }
        )
    return facts


async def stream_txt(facts: list[dict]) -> AsyncIterator[str]:
    """Stream facts as plain text."""
    for f in facts:
        yield f"[{f['seq']}] [{f['node']}] {f['sentence']}\n"


async def stream_json(facts: list[dict]) -> AsyncIterator[str]:
    """Stream facts as JSON array."""
    yield json.dumps(facts, default=str, indent=2)


async def stream_ndjson(facts: list[dict]) -> AsyncIterator[str]:
    """Stream facts as newline-delimited JSON."""
    for f in facts:
        yield json.dumps(f, default=str) + "\n"


async def stream_csv(facts: list[dict]) -> AsyncIterator[str]:
    """Stream facts as CSV."""
    if not facts:
        return
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=facts[0].keys())
    writer.writeheader()
    yield buf.getvalue()
    buf.truncate(0)
    buf.seek(0)
    for f in facts:
        writer.writerow(f)
        yield buf.getvalue()
        buf.truncate(0)
        buf.seek(0)


async def export_facts(
    db: AsyncSession,
    fmt: str,
    node_uids: list,
    state_filter: list[str],
    actor: FcUser,
) -> AsyncIterator[str]:
    """Export facts in the requested format after permission check."""
    has_access = False
    for uid in node_uids:
        if await can(actor, "read", uid, db):
            has_access = True
            break
    if not has_access:
        raise Forbidden("No read access to any of the requested nodes")

    facts = await load_facts_for_export(db, node_uids, state_filter)

    if fmt == "txt":
        return stream_txt(facts)
    elif fmt == "ndjson":
        return stream_ndjson(facts)
    elif fmt == "csv":
        return stream_csv(facts)
    else:
        return stream_json(facts)
