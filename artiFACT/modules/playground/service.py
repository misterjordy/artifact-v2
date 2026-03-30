"""Playground reset logic: restore database to golden snapshot state."""

from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger()

GOLDEN_SNAPSHOT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "golden_snapshot.sql"

# Delete order respects FK constraints
DELETE_STATEMENTS = [
    "DELETE FROM fc_event_log",
    "DELETE FROM fc_node_permission",
    "UPDATE fc_fact SET current_published_version_uid = NULL, current_signed_version_uid = NULL",
    "DELETE FROM fc_fact_version",
    "DELETE FROM fc_fact",
    "DELETE FROM fc_node",
    "DELETE FROM fc_document_template",
    "DELETE FROM fc_user WHERE cac_dn IN ('jallred', 'dwallace', 'omartinez', 'pbeesly')",
]

# SQL prefixes that should be executed from the snapshot
EXECUTABLE_PREFIXES = ("INSERT INTO", "SELECT", "ALTER TABLE")


async def reset_to_golden(db: AsyncSession) -> None:
    """Wipe seeded data and restore from golden snapshot SQL.

    Must be called inside a transaction (async with db.begin()).
    """
    log.info("playground_reset_starting")

    # 1. Delete in FK-safe order
    for stmt in DELETE_STATEMENTS:
        await db.execute(text(stmt))
    log.info("playground_tables_cleared")

    # 2. Disable FK trigger checks during restore — pg_dump --inserts
    # doesn't guarantee FK-safe order for self-referencing tables
    # (fc_node.parent_node_uid, fc_fact_version.supersedes_version_uid)
    # or circular FKs (fc_fact ↔ fc_fact_version).
    await db.execute(text("SET session_replication_role = 'replica'"))

    # 3. Load and execute golden snapshot
    if not GOLDEN_SNAPSHOT_PATH.exists():
        log.error("golden_snapshot_not_found", path=str(GOLDEN_SNAPSHOT_PATH))
        raise FileNotFoundError(f"Golden snapshot not found: {GOLDEN_SNAPSHOT_PATH}")

    snapshot_sql = GOLDEN_SNAPSHOT_PATH.read_text(encoding="utf-8")

    # Execute valid SQL lines from pg_dump output
    # Skip: comments (--), psql meta-commands (\), SET statements,
    # and pg_catalog.set_config which corrupts the connection's search_path
    executed = 0
    for line in snapshot_sql.split("\n"):
        line = line.strip()
        if not line or line.startswith("--") or line.startswith("\\"):
            continue

        upper = line.upper()

        # pg_dump emits set_config('search_path', '', false) which blanks the
        # search_path on the pooled connection, breaking all later queries.
        if "SET_CONFIG" in upper.replace(" ", "_") and "SEARCH_PATH" in upper:
            continue

        if any(upper.startswith(prefix) for prefix in EXECUTABLE_PREFIXES):
            await db.execute(text(line))
            executed += 1
        elif upper.startswith("SET SESSION AUTHORIZATION"):
            await db.execute(text(line))
            executed += 1

    # 4. Re-enable FK triggers and restore search_path
    await db.execute(text("SET session_replication_role = 'origin'"))
    await db.execute(text("SET search_path = public"))

    log.info("playground_reset_complete", statements_executed=executed)
