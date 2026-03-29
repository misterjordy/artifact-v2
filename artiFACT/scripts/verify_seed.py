"""Verify seeded v2 database integrity. Exits non-zero on any failure."""

import asyncio
import os
import sys
import uuid
from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

from artiFACT.kernel.config import settings

log = structlog.get_logger()

FAILURES: list[str] = []


def check(condition: bool, msg: str) -> None:
    """Assert a condition, recording failure if false."""
    if not condition:
        FAILURES.append(msg)
        log.error("FAIL", check=msg)
    else:
        log.info("PASS", check=msg)


async def _scalar(db: AsyncSession, query: str) -> int:
    result = await db.execute(text(query))
    return result.scalar() or 0


async def _fetchall(db: AsyncSession, query: str) -> list:
    result = await db.execute(text(query))
    return list(result.fetchall())


async def _fetchone(db: AsyncSession, query: str):
    result = await db.execute(text(query))
    return result.fetchone()


async def verify_row_counts(db: AsyncSession) -> None:
    """Verify exact row counts for all seeded tables."""
    log.info("--- Row Counts ---")

    user_count = await _scalar(db, "SELECT COUNT(*) FROM fc_user")
    check(user_count == 4, f"fc_user count == 4 (got {user_count})")

    node_count = await _scalar(db, "SELECT COUNT(*) FROM fc_node")
    check(node_count == 214, f"fc_node count == 214 (got {node_count})")

    fact_count = await _scalar(db, "SELECT COUNT(*) FROM fc_fact")
    check(fact_count == 719, f"fc_fact count == 719 (got {fact_count})")

    version_count = await _scalar(db, "SELECT COUNT(*) FROM fc_fact_version")
    check(version_count == 744, f"fc_fact_version count == 744 (got {version_count})")

    perm_count = await _scalar(db, "SELECT COUNT(*) FROM fc_node_permission")
    check(perm_count >= 5, f"fc_node_permission count >= 5 (got {perm_count})")

    event_count = await _scalar(db, "SELECT COUNT(*) FROM fc_event_log")
    check(event_count >= 744, f"fc_event_log count >= 744 (got {event_count})")


async def verify_tree_integrity(db: AsyncSession) -> None:
    """Verify tree structure: root, programs, orphans, depth."""
    log.info("--- Tree Integrity ---")

    # Root exists and is singular
    roots = await _fetchall(
        db, "SELECT node_uid, title, node_depth FROM fc_node WHERE parent_node_uid IS NULL"
    )
    check(len(roots) == 1, f"exactly 1 root node (got {len(roots)})")
    if roots:
        check(roots[0][1] == "Special Projects", f"root title == 'Special Projects' (got '{roots[0][1]}')")
        check(roots[0][2] == 0, f"root node_depth == 0 (got {roots[0][2]})")
        root_uid = roots[0][0]
    else:
        return

    # Both programs exist as children of root
    programs = await _fetchall(
        db,
        f"SELECT title, node_depth FROM fc_node "
        f"WHERE parent_node_uid = '{root_uid}' ORDER BY title",
    )
    check(len(programs) == 2, f"2 program nodes (got {len(programs)})")
    if len(programs) >= 2:
        check(programs[0][0] == "Boatwing H-12", f"first program == 'Boatwing H-12' (got '{programs[0][0]}')")
        check(programs[0][1] == 1, f"Boatwing depth == 1 (got {programs[0][1]})")
        check(programs[1][0] == "SNIPE-B", f"second program == 'SNIPE-B' (got '{programs[1][0]}')")
        check(programs[1][1] == 1, f"SNIPE-B depth == 1 (got {programs[1][1]})")

    # No orphaned nodes
    orphans = await _scalar(
        db,
        "SELECT COUNT(*) FROM fc_node n "
        "LEFT JOIN fc_node p ON n.parent_node_uid = p.node_uid "
        "WHERE n.parent_node_uid IS NOT NULL AND p.node_uid IS NULL",
    )
    check(orphans == 0, f"no orphaned nodes (got {orphans})")

    # Verify node_depth by walking parent chain (sample 20 deep nodes)
    deep_nodes = await _fetchall(
        db,
        "SELECT node_uid, title, node_depth FROM fc_node "
        "WHERE node_depth >= 3 ORDER BY random() LIMIT 20",
    )
    for row in deep_nodes:
        nuid, ntitle, stored_depth = row
        actual = await _compute_depth(db, nuid)
        check(
            stored_depth == actual,
            f"depth check '{ntitle}': stored={stored_depth}, computed={actual}",
        )

    # No false roots
    false_roots = await _scalar(
        db,
        "SELECT COUNT(*) FROM fc_node WHERE node_depth = 0 AND parent_node_uid IS NOT NULL",
    )
    check(false_roots == 0, f"no depth=0 nodes with parent (got {false_roots})")


async def _compute_depth(db: AsyncSession, node_uid: uuid.UUID) -> int:
    """Walk parent chain to compute actual depth."""
    depth = 0
    current = node_uid
    for _ in range(10):  # safety limit
        row = await _fetchone(
            db, f"SELECT parent_node_uid FROM fc_node WHERE node_uid = '{current}'"
        )
        if not row or row[0] is None:
            break
        depth += 1
        current = row[0]
    return depth


async def verify_fact_integrity(db: AsyncSession) -> None:
    """Verify fact data integrity."""
    log.info("--- Fact Integrity ---")

    # Every fact references a real node
    dangling = await _scalar(
        db,
        "SELECT COUNT(*) FROM fc_fact f "
        "LEFT JOIN fc_node n ON f.node_uid = n.node_uid "
        "WHERE n.node_uid IS NULL",
    )
    check(dangling == 0, f"no dangling fact→node refs (got {dangling})")

    # Every published fact has current_published_version_uid set
    broken_pub = await _scalar(
        db,
        "SELECT COUNT(*) FROM fc_fact "
        "WHERE NOT is_retired "
        "AND current_published_version_uid IS NULL "
        "AND fact_uid IN ("
        "  SELECT DISTINCT fact_uid FROM fc_fact_version WHERE state = 'published'"
        ")",
    )
    check(broken_pub == 0, f"no published facts missing current_published_version_uid (got {broken_pub})")

    # current_published_version_uid points to published version
    bad_ptr = await _scalar(
        db,
        "SELECT COUNT(*) FROM fc_fact f "
        "JOIN fc_fact_version v ON f.current_published_version_uid = v.version_uid "
        "WHERE v.state != 'published'",
    )
    check(bad_ptr == 0, f"no current_published_version_uid pointing to non-published (got {bad_ptr})")

    # No empty sentences
    empty = await _scalar(
        db,
        "SELECT COUNT(*) FROM fc_fact_version "
        "WHERE display_sentence IS NULL OR display_sentence = ''",
    )
    check(empty == 0, f"no empty display_sentence (got {empty})")

    # No suspiciously short sentences
    short = await _scalar(
        db,
        "SELECT COUNT(*) FROM fc_fact_version WHERE length(display_sentence) < 10",
    )
    check(short == 0, f"no suspiciously short sentences (got {short})")

    # Version→fact FK integrity
    dangling_ver = await _scalar(
        db,
        "SELECT COUNT(*) FROM fc_fact_version v "
        "LEFT JOIN fc_fact f ON v.fact_uid = f.fact_uid "
        "WHERE f.fact_uid IS NULL",
    )
    check(dangling_ver == 0, f"no dangling version→fact refs (got {dangling_ver})")


async def verify_user_permissions(db: AsyncSession) -> None:
    """Verify user and permission integrity."""
    log.info("--- User & Permission Integrity ---")

    # Check each user
    for username, expected_role in [
        ("jallred", "admin"), ("dwallace", "viewer"),
        ("omartinez", "viewer"), ("pbeesly", "viewer"),
    ]:
        row = await _fetchone(
            db,
            f"SELECT global_role, is_active FROM fc_user WHERE cac_dn = '{username}'",
        )
        check(row is not None, f"user '{username}' exists")
        if row:
            check(row[0] == expected_role, f"{username} global_role == '{expected_role}' (got '{row[0]}')")
            check(row[1] is True, f"{username} is_active")

    # dwallace is signatory on root
    dw_sig = await _fetchall(
        db,
        "SELECT p.role FROM fc_node_permission p "
        "JOIN fc_user u ON p.user_uid = u.user_uid "
        "JOIN fc_node n ON p.node_uid = n.node_uid "
        "WHERE u.cac_dn = 'dwallace' AND n.parent_node_uid IS NULL "
        "AND p.revoked_at IS NULL",
    )
    check(len(dw_sig) == 1, f"dwallace has 1 permission on root (got {len(dw_sig)})")
    if dw_sig:
        check(dw_sig[0][0] == "signatory", f"dwallace role on root == 'signatory' (got '{dw_sig[0][0]}')")

    # omartinez is approver on BOTH program nodes
    om_perms = await _fetchall(
        db,
        "SELECT p.role, n.title FROM fc_node_permission p "
        "JOIN fc_user u ON p.user_uid = u.user_uid "
        "JOIN fc_node n ON p.node_uid = n.node_uid "
        "WHERE u.cac_dn = 'omartinez' AND p.revoked_at IS NULL",
    )
    check(len(om_perms) == 2, f"omartinez has 2 permissions (got {len(om_perms)})")
    check(
        all(p[0] == "approver" for p in om_perms),
        f"omartinez all roles == 'approver' (got {[p[0] for p in om_perms]})",
    )

    # pbeesly is contributor on BOTH program nodes
    pb_perms = await _fetchall(
        db,
        "SELECT p.role, n.title FROM fc_node_permission p "
        "JOIN fc_user u ON p.user_uid = u.user_uid "
        "JOIN fc_node n ON p.node_uid = n.node_uid "
        "WHERE u.cac_dn = 'pbeesly' AND p.revoked_at IS NULL",
    )
    check(len(pb_perms) == 2, f"pbeesly has 2 permissions (got {len(pb_perms)})")
    check(
        all(p[0] == "contributor" for p in pb_perms),
        f"pbeesly all roles == 'contributor' (got {[p[0] for p in pb_perms]})",
    )

    # NEGATIVE: dwallace has no non-signatory permissions
    dw_bad = await _scalar(
        db,
        "SELECT COUNT(*) FROM fc_node_permission p "
        "JOIN fc_user u ON p.user_uid = u.user_uid "
        "WHERE u.cac_dn = 'dwallace' AND p.role != 'signatory' AND p.revoked_at IS NULL",
    )
    check(dw_bad == 0, f"dwallace has no non-signatory perms (got {dw_bad})")

    # NEGATIVE: pbeesly has no non-contributor permissions
    pb_bad = await _scalar(
        db,
        "SELECT COUNT(*) FROM fc_node_permission p "
        "JOIN fc_user u ON p.user_uid = u.user_uid "
        "WHERE u.cac_dn = 'pbeesly' AND p.role != 'contributor' AND p.revoked_at IS NULL",
    )
    check(pb_bad == 0, f"pbeesly has no non-contributor perms (got {pb_bad})")


async def verify_event_log(db: AsyncSession) -> None:
    """Verify event log integrity."""
    log.info("--- Event Log Integrity ---")

    event_count = await _scalar(db, "SELECT COUNT(*) FROM fc_event_log")
    version_count = await _scalar(db, "SELECT COUNT(*) FROM fc_fact_version")
    check(event_count >= version_count, f"events ({event_count}) >= versions ({version_count})")

    # Every event references a real entity
    dangling = await _scalar(
        db,
        "SELECT COUNT(*) FROM fc_event_log e "
        "WHERE e.entity_type = 'version' "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM fc_fact_version v WHERE v.version_uid = e.entity_uid"
        ")",
    )
    check(dangling == 0, f"no dangling event→version refs (got {dangling})")

    # Published versions have both proposed AND published events
    pub_versions = await _fetchall(
        db, "SELECT version_uid FROM fc_fact_version WHERE state = 'published'"
    )
    missing_proposed = 0
    missing_published = 0
    for row in pub_versions:
        vuid = row[0]
        events = await _fetchall(
            db,
            f"SELECT event_type FROM fc_event_log WHERE entity_uid = '{vuid}'",
        )
        types = {e[0] for e in events}
        if "fact.proposed" not in types:
            missing_proposed += 1
        if "fact.published" not in types:
            missing_published += 1

    check(missing_proposed == 0, f"all published versions have proposed event (missing {missing_proposed})")
    check(missing_published == 0, f"all published versions have published event (missing {missing_published})")

    # Timestamps sane: proposed before published
    bad_order = await _scalar(
        db,
        "SELECT COUNT(*) FROM fc_event_log e1 "
        "JOIN fc_event_log e2 ON e1.entity_uid = e2.entity_uid "
        "WHERE e1.event_type = 'fact.proposed' AND e2.event_type = 'fact.published' "
        "AND e1.occurred_at > e2.occurred_at",
    )
    check(bad_order == 0, f"no proposed-after-published timestamp errors (got {bad_order})")


async def verify_golden_snapshot() -> None:
    """Verify golden snapshot file exists and has expected content."""
    log.info("--- Golden Snapshot ---")

    snapshot_path = Path("/app/artiFACT/scripts/golden_snapshot.sql")
    check(snapshot_path.exists(), f"golden_snapshot.sql exists at {snapshot_path}")

    if not snapshot_path.exists():
        return

    size = snapshot_path.stat().st_size
    check(size > 100_000, f"golden_snapshot.sql > 100KB (got {size} bytes)")

    content = snapshot_path.read_text()
    for table in [
        "fc_user", "fc_node", "fc_node_permission",
        "fc_fact", "fc_fact_version", "fc_event_log",
    ]:
        has_insert = "INSERT INTO" in content and table in content
        check(has_insert, f"golden_snapshot contains INSERT for {table}")


async def verify_idempotency() -> None:
    """Verify that running the seed script again does not change counts."""
    log.info("--- Idempotency ---")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    tables = ["fc_user", "fc_node", "fc_fact", "fc_fact_version"]

    async with sf() as db:
        before = {}
        for t in tables:
            before[t] = await _scalar(db, f"SELECT COUNT(*) FROM {t}")

    # Re-run seed (creates its own engine/session)
    from artiFACT.scripts.seed_v1_data import run_seed
    await run_seed()

    async with sf() as db:
        after = {}
        for t in tables:
            after[t] = await _scalar(db, f"SELECT COUNT(*) FROM {t}")

    await engine.dispose()
    check(before == after, f"idempotent: before={before}, after={after}")


async def main() -> None:
    """Run all verification checks."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as db:
        await verify_row_counts(db)
        await verify_tree_integrity(db)
        await verify_fact_integrity(db)
        await verify_user_permissions(db)
        await verify_event_log(db)

    await engine.dispose()

    await verify_golden_snapshot()

    # Idempotency check (creates its own session)
    await verify_idempotency()

    # Report
    total = len(FAILURES)
    if total > 0:
        log.error("verification_failed", failures=total)
        for f in FAILURES:
            print(f"  FAIL: {f}", file=sys.stderr)
        sys.exit(1)
    else:
        log.info("all_checks_passed")
        print("All verification checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
