"""Verify the artiFACT self-documenting compliance corpus.

Runs 7 verification checks against the seeded data.

Run: docker compose exec web python -m artiFACT.scripts.verify_artifact_corpus
"""

import asyncio
import sys
from pathlib import Path

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from artiFACT.kernel.config import settings
from artiFACT.kernel.models import (
    FcDocumentTemplate,
    FcFact,
    FcFactVersion,
    FcNode,
    FcNodePermission,
)

log = structlog.get_logger()

PLAYGROUND_USERS = [
    "a0000002-0000-4000-8000-000000000002",  # dwallace
    "a0000003-0000-4000-8000-000000000003",  # omartinez
    "a0000004-0000-4000-8000-000000000004",  # pbeesly
]
JALLRED_UID = "a0000001-0000-4000-8000-000000000001"

GOLDEN_SNAPSHOT_PATH = Path("/app/artiFACT/scripts/golden_snapshot.sql")


class VerifyError(Exception):
    pass


def _assert(condition: bool, msg: str) -> None:
    if not condition:
        raise VerifyError(msg)


async def _get_artifact_node(db: AsyncSession) -> tuple:
    """Return (node_uid, node) for the artiFACT program node."""
    result = await db.execute(
        select(FcNode).where(FcNode.title == "artiFACT", FcNode.node_depth == 0)
    )
    node = result.scalar_one_or_none()
    _assert(node is not None, "artiFACT node not found at depth 0")
    return node.node_uid, node


async def _get_descendant_uids(db: AsyncSession, root_uid) -> list:
    """Get all descendant node UIDs using recursive CTE."""
    cte_sql = text("""
        WITH RECURSIVE descendants AS (
            SELECT node_uid FROM fc_node WHERE parent_node_uid = :root_uid
            UNION ALL
            SELECT n.node_uid FROM fc_node n
            JOIN descendants d ON n.parent_node_uid = d.node_uid
        )
        SELECT node_uid FROM descendants
    """)
    result = await db.execute(cte_sql, {"root_uid": root_uid})
    return [row[0] for row in result.fetchall()]


async def verify_1_node_count(db: AsyncSession) -> None:
    """VERIFY 1: Node count."""
    print("VERIFY 1 — Node count...")

    # Exactly 1 artiFACT node at depth 1
    result = await db.execute(
        select(func.count()).select_from(FcNode).where(
            FcNode.title == "artiFACT", FcNode.node_depth == 0
        )
    )
    count = result.scalar()
    _assert(count == 1, f"Expected exactly 1 artiFACT node at depth 0, got {count}")

    artifact_uid, _ = await _get_artifact_node(db)
    descendants = await _get_descendant_uids(db, artifact_uid)
    desc_count = len(descendants)
    _assert(
        desc_count >= 50,
        f"Expected >= 50 descendant nodes, got {desc_count}",
    )
    print(f"  PASS: 1 artiFACT node, {desc_count} descendants")


async def verify_2_fact_count(db: AsyncSession) -> None:
    """VERIFY 2: Fact count >= 200."""
    print("VERIFY 2 — Fact count...")

    artifact_uid, _ = await _get_artifact_node(db)
    descendant_uids = await _get_descendant_uids(db, artifact_uid)
    all_node_uids = [artifact_uid] + descendant_uids

    result = await db.execute(
        select(func.count()).select_from(FcFact).where(
            FcFact.node_uid.in_(all_node_uids)
        )
    )
    fact_count = result.scalar()
    _assert(fact_count >= 200, f"Expected >= 200 facts, got {fact_count}")
    print(f"  PASS: {fact_count} facts under artiFACT subtree")


async def verify_3_all_published(db: AsyncSession) -> None:
    """VERIFY 3: All facts published."""
    print("VERIFY 3 — All facts published...")

    artifact_uid, _ = await _get_artifact_node(db)
    descendant_uids = await _get_descendant_uids(db, artifact_uid)
    all_node_uids = [artifact_uid] + descendant_uids

    # Get fact UIDs under artiFACT subtree
    fact_result = await db.execute(
        select(FcFact.fact_uid).where(FcFact.node_uid.in_(all_node_uids))
    )
    fact_uids = [row[0] for row in fact_result.fetchall()]

    if not fact_uids:
        raise VerifyError("No facts found under artiFACT subtree")

    # Count non-published versions for these facts
    result = await db.execute(
        select(func.count()).select_from(FcFactVersion).where(
            FcFactVersion.fact_uid.in_(fact_uids),
            FcFactVersion.state != "published",
        )
    )
    non_published = result.scalar()
    _assert(non_published == 0, f"Expected 0 non-published versions, got {non_published}")
    print(f"  PASS: All {len(fact_uids)} fact versions are published")


async def verify_4_document_templates(db: AsyncSession) -> None:
    """VERIFY 4: Document templates."""
    print("VERIFY 4 — Document templates...")

    required = ["ConOps", "SDD", "SSP", "TEMP", "SEP"]
    for abbr in required:
        result = await db.execute(
            select(FcDocumentTemplate).where(
                FcDocumentTemplate.abbreviation == abbr
            )
        )
        tmpl = result.scalar_one_or_none()
        _assert(tmpl is not None, f"Template {abbr} not found")
        _assert(
            isinstance(tmpl.sections, list) and len(tmpl.sections) > 0,
            f"Template {abbr} has empty sections",
        )
        for section in tmpl.sections:
            for field in ("key", "title", "prompt", "guidance"):
                _assert(
                    field in section,
                    f"Template {abbr} section missing '{field}': {section}",
                )
    print(f"  PASS: All 5 templates present with valid sections")


async def verify_5_diagram_facts(db: AsyncSession) -> None:
    """VERIFY 5: Diagram facts tagged."""
    print("VERIFY 5 — Diagram facts tagged...")

    # Find Diagrams node
    artifact_uid, _ = await _get_artifact_node(db)
    result = await db.execute(
        select(FcNode).where(
            FcNode.title == "Diagrams",
            FcNode.parent_node_uid == artifact_uid,
        )
    )
    diagrams_node = result.scalar_one_or_none()
    _assert(diagrams_node is not None, "Diagrams node not found")

    diagram_descendants = await _get_descendant_uids(db, diagrams_node.node_uid)
    all_diagram_uids = [diagrams_node.node_uid] + diagram_descendants

    # Get facts under Diagrams
    fact_result = await db.execute(
        select(FcFact.fact_uid).where(FcFact.node_uid.in_(all_diagram_uids))
    )
    fact_uids = [row[0] for row in fact_result.fetchall()]
    _assert(len(fact_uids) >= 30, f"Expected >= 30 diagram facts, got {len(fact_uids)}")

    # Check all start with DIAGRAM:MERMAID:
    version_result = await db.execute(
        select(FcFactVersion.display_sentence).where(
            FcFactVersion.fact_uid.in_(fact_uids),
            FcFactVersion.state == "published",
        )
    )
    sentences = [row[0] for row in version_result.fetchall()]
    for s in sentences:
        _assert(
            s.startswith("DIAGRAM:MERMAID:"),
            f"Diagram fact does not start with DIAGRAM:MERMAID: — '{s[:60]}'",
        )
    print(f"  PASS: {len(fact_uids)} diagram facts, all tagged DIAGRAM:MERMAID:")


async def verify_6_admin_only(db: AsyncSession) -> None:
    """VERIFY 6: Admin-only visibility."""
    print("VERIFY 6 — Admin-only visibility...")

    artifact_uid, _ = await _get_artifact_node(db)
    descendant_uids = await _get_descendant_uids(db, artifact_uid)
    all_node_uids = [artifact_uid] + descendant_uids

    # Check jallred has permission
    result = await db.execute(
        select(FcNodePermission).where(
            FcNodePermission.user_uid == JALLRED_UID,
            FcNodePermission.node_uid == artifact_uid,
            FcNodePermission.revoked_at.is_(None),
        )
    )
    jallred_perm = result.scalar_one_or_none()
    _assert(jallred_perm is not None, "jallred has no permission on artiFACT node")

    # Check no playground users have permissions on artiFACT or descendants
    for user_uid in PLAYGROUND_USERS:
        result = await db.execute(
            select(func.count()).select_from(FcNodePermission).where(
                FcNodePermission.user_uid == user_uid,
                FcNodePermission.node_uid.in_(all_node_uids),
                FcNodePermission.revoked_at.is_(None),
            )
        )
        count = result.scalar()
        _assert(
            count == 0,
            f"Playground user {user_uid} has {count} permissions on artiFACT subtree",
        )
    print("  PASS: Only jallred has permissions on artiFACT subtree")


async def verify_7_golden_snapshot(db: AsyncSession) -> None:
    """VERIFY 7: Golden snapshot updated."""
    print("VERIFY 7 — Golden snapshot updated...")

    _assert(
        GOLDEN_SNAPSHOT_PATH.exists(),
        f"Golden snapshot not found at {GOLDEN_SNAPSHOT_PATH}",
    )

    content = GOLDEN_SNAPSHOT_PATH.read_text(encoding="utf-8")
    _assert(
        "artiFACT" in content,
        "Golden snapshot does not contain artiFACT node data",
    )

    size = GOLDEN_SNAPSHOT_PATH.stat().st_size
    _assert(size > 1_000_000, f"Golden snapshot seems too small: {size} bytes")
    print(f"  PASS: Golden snapshot contains artiFACT data ({size:,} bytes)")


async def run_verify() -> None:
    """Run all verification checks."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    passed = 0
    failed = 0

    async with session_factory() as db:
        checks = [
            verify_1_node_count,
            verify_2_fact_count,
            verify_3_all_published,
            verify_4_document_templates,
            verify_5_diagram_facts,
            verify_6_admin_only,
            verify_7_golden_snapshot,
        ]
        for check in checks:
            try:
                await check(db)
                passed += 1
            except VerifyError as e:
                print(f"  FAIL: {e}")
                failed += 1
            except Exception as e:
                print(f"  ERROR: {e}")
                failed += 1

    await engine.dispose()

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)
    print("All checks passed!")


if __name__ == "__main__":
    asyncio.run(run_verify())
