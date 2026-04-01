"""Playground reset logic: program-scoped wipe and restore.

Wipes only data under the Special Projects root node and restores it
from playground_snapshot.sql. All other programs (artiFACT corpus,
future live programs), global tables, and the admin user are preserved.
"""

from pathlib import Path
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.tree.descendants import get_descendants

log = structlog.get_logger()

PLAYGROUND_ROOT_TITLE = "Special Projects"
PLAYGROUND_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "playground_snapshot.sql"
)
PLAYGROUND_USERNAMES: tuple[str, ...] = (
    "dwallace", "omartinez", "pbeesly", "mscott", "mpalmer", "jhalpert", "cbratton",
)
_EXECUTABLE_PREFIXES = ("INSERT INTO", "SELECT", "ALTER TABLE", "UPDATE")


async def _find_playground_root(db: AsyncSession) -> UUID:
    """Find the Special Projects root node UID by title."""
    result = await db.execute(
        text("SELECT node_uid FROM fc_node WHERE title = :title AND parent_node_uid IS NULL"),
        {"title": PLAYGROUND_ROOT_TITLE},
    )
    row = result.one_or_none()
    if row is None:
        raise ValueError(f"Root node '{PLAYGROUND_ROOT_TITLE}' not found")
    return row[0]


async def _collect_target_ids(db: AsyncSession, root_uid: UUID) -> int:
    """Create temp tables with all playground entity IDs. Returns node count."""
    node_uids = await get_descendants(db, root_uid)
    if not node_uids:
        return 0

    await db.execute(text("CREATE TEMP TABLE _pg_nodes (uid UUID) ON COMMIT DROP"))
    await db.execute(text("CREATE TEMP TABLE _pg_facts (uid UUID) ON COMMIT DROP"))
    await db.execute(text("CREATE TEMP TABLE _pg_versions (uid UUID) ON COMMIT DROP"))
    await db.execute(text("CREATE TEMP TABLE _pg_comments (uid UUID) ON COMMIT DROP"))
    await db.execute(text("CREATE TEMP TABLE _pg_sigs (uid UUID) ON COMMIT DROP"))

    for uid in node_uids:
        await db.execute(text("INSERT INTO _pg_nodes VALUES (:uid)"), {"uid": str(uid)})

    await db.execute(text(
        "INSERT INTO _pg_facts SELECT fact_uid FROM fc_fact "
        "WHERE node_uid IN (SELECT uid FROM _pg_nodes)"
    ))
    await db.execute(text(
        "INSERT INTO _pg_versions SELECT version_uid FROM fc_fact_version "
        "WHERE fact_uid IN (SELECT uid FROM _pg_facts)"
    ))
    await db.execute(text(
        "INSERT INTO _pg_comments SELECT comment_uid FROM fc_fact_comment "
        "WHERE version_uid IN (SELECT uid FROM _pg_versions)"
    ))
    await db.execute(text(
        "INSERT INTO _pg_sigs SELECT signature_uid FROM fc_signature "
        "WHERE node_uid IN (SELECT uid FROM _pg_nodes)"
    ))
    return len(node_uids)


async def _delete_scoped_data(db: AsyncSession) -> None:
    """Delete playground data in FK-safe order using pre-collected temp tables."""
    # a. Comments
    await db.execute(text(
        "DELETE FROM fc_fact_comment WHERE comment_uid IN (SELECT uid FROM _pg_comments)"
    ))
    # b. Event log entries referencing playground entities
    await db.execute(text(
        "DELETE FROM fc_event_log WHERE entity_uid IN ("
        "SELECT uid FROM _pg_nodes UNION ALL SELECT uid FROM _pg_facts UNION ALL "
        "SELECT uid FROM _pg_versions UNION ALL SELECT uid FROM _pg_comments UNION ALL "
        "SELECT uid FROM _pg_sigs)"
    ))
    # c. Signatures
    await db.execute(text(
        "DELETE FROM fc_signature WHERE signature_uid IN (SELECT uid FROM _pg_sigs)"
    ))
    # d. NULL out fact version pointers
    await db.execute(text(
        "UPDATE fc_fact SET current_published_version_uid = NULL, "
        "current_signed_version_uid = NULL "
        "WHERE fact_uid IN (SELECT uid FROM _pg_facts)"
    ))
    # d2. Import staged facts (FK to fc_fact_version via duplicate_of_uid/conflict_with_uid)
    await db.execute(text(
        "DELETE FROM fc_import_staged_fact WHERE session_uid IN ("
        "SELECT session_uid FROM fc_import_session "
        "WHERE program_node_uid IN (SELECT uid FROM _pg_nodes))"
    ))
    # e. Versions
    await db.execute(text(
        "DELETE FROM fc_fact_version WHERE version_uid IN (SELECT uid FROM _pg_versions)"
    ))
    # f. Facts
    await db.execute(text(
        "DELETE FROM fc_fact WHERE fact_uid IN (SELECT uid FROM _pg_facts)"
    ))
    # g. Node permissions
    await db.execute(text(
        "DELETE FROM fc_node_permission WHERE node_uid IN (SELECT uid FROM _pg_nodes)"
    ))
    # h. Import sessions
    await db.execute(text(
        "DELETE FROM fc_import_session WHERE program_node_uid IN (SELECT uid FROM _pg_nodes)"
    ))
    # i. Nodes in reverse depth order (leaves first — ON DELETE RESTRICT)
    result = await db.execute(text(
        "SELECT DISTINCT node_depth FROM fc_node "
        "WHERE node_uid IN (SELECT uid FROM _pg_nodes) ORDER BY node_depth DESC"
    ))
    for row in result.all():
        await db.execute(text(
            "DELETE FROM fc_node WHERE node_uid IN (SELECT uid FROM _pg_nodes) "
            "AND node_depth = :d"
        ), {"d": row[0]})


async def _delete_playground_users(db: AsyncSession) -> None:
    """Delete playground-only users (Office characters). Never deletes jallred."""
    # Build a safe IN list from the constant tuple (not user input)
    in_list = ", ".join(f"'{u}'" for u in PLAYGROUND_USERNAMES)
    user_subq = f"SELECT user_uid FROM fc_user WHERE cac_dn IN ({in_list})"
    # Remove chat messages + sessions (no CASCADE from user to chat tables via session)
    await db.execute(text(
        f"DELETE FROM fc_chat_message WHERE chat_uid IN ("
        f"SELECT chat_uid FROM fc_chat_session WHERE user_uid IN ({user_subq}))"
    ))
    await db.execute(text(f"DELETE FROM fc_chat_session WHERE user_uid IN ({user_subq})"))
    # Remove AI usage records (no CASCADE on FK)
    await db.execute(text(f"DELETE FROM fc_ai_usage WHERE user_uid IN ({user_subq})"))
    # NULL out remaining event_log actor refs for safety
    await db.execute(text(
        f"UPDATE fc_event_log SET actor_uid = NULL WHERE actor_uid IN ({user_subq})"
    ))
    # Delete users (api_key, ai_key, preferences CASCADE automatically)
    await db.execute(text(f"DELETE FROM fc_user WHERE cac_dn IN ({in_list})"))


async def _restore_from_snapshot(db: AsyncSession) -> int:
    """Load playground_snapshot.sql. Returns count of statements executed."""
    if not PLAYGROUND_SNAPSHOT_PATH.exists():
        log.error("playground_snapshot_not_found", path=str(PLAYGROUND_SNAPSHOT_PATH))
        raise FileNotFoundError(f"Playground snapshot not found: {PLAYGROUND_SNAPSHOT_PATH}")

    snapshot_sql = PLAYGROUND_SNAPSHOT_PATH.read_text(encoding="utf-8")

    # Disable FK triggers — snapshot doesn't guarantee FK-safe order for
    # self-referencing tables and circular FKs (fc_fact <-> fc_fact_version)
    await db.execute(text("SET session_replication_role = 'replica'"))

    executed = 0
    for line in snapshot_sql.split("\n"):
        line = line.strip()
        if not line or line.startswith("--") or line.startswith("\\"):
            continue
        upper = line.upper()
        # Skip set_config('search_path', ...) which breaks pooled connections
        if "SET_CONFIG" in upper.replace(" ", "_") and "SEARCH_PATH" in upper:
            continue
        if any(upper.startswith(p) for p in _EXECUTABLE_PREFIXES):
            await db.execute(text(line))
            executed += 1
        elif upper.startswith("SET SESSION AUTHORIZATION"):
            await db.execute(text(line))
            executed += 1

    # Re-enable FK triggers and restore search_path
    await db.execute(text("SET session_replication_role = 'origin'"))
    await db.execute(text("SET search_path = public"))
    return executed


async def reset_playground(db: AsyncSession) -> None:
    """Wipe playground data under Special Projects and restore from snapshot.

    Preserves all other programs (artiFACT corpus, future live programs),
    global tables (system_config, document_templates), and the admin user.
    Must be called inside a transaction (the caller commits).
    """
    log.info("playground_reset_starting")

    root_uid = await _find_playground_root(db)
    node_count = await _collect_target_ids(db, root_uid)
    log.info("playground_target_collected", nodes=node_count)

    await _delete_scoped_data(db)
    await _delete_playground_users(db)
    log.info("playground_data_deleted")

    executed = await _restore_from_snapshot(db)
    log.info("playground_reset_complete", statements_executed=executed)
