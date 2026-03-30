"""Generate playground_snapshot.sql from the current database.

Extracts only data under the Special Projects root:
  - Playground-only users (dwallace, omartinez, pbeesly, etc.)
  - Special Projects node tree (depth order)
  - Node permissions on those nodes
  - Facts under those nodes
  - Versions (with supersedes chain)
  - Fact pointer UPDATEs (current_published_version_uid)
  - Comments on playground versions
  - Signatures on playground nodes
  - Events for playground entities (seq omitted — DB assigns new values)

Usage:
  docker compose exec web python -m artiFACT.scripts.generate_playground_snapshot
"""

import asyncio
import json
from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from artiFACT.kernel.config import settings

log = structlog.get_logger()

OUTPUT_PATH = Path(__file__).resolve().parent / "playground_snapshot.sql"
PLAYGROUND_ROOT_TITLE = "Special Projects"
PLAYGROUND_USERNAMES = (
    "dwallace", "omartinez", "pbeesly", "mscott", "mpalmer", "jhalpert", "cbratton",
)


def _sql_val(val: object) -> str:
    """Format a Python value as a SQL literal."""
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, dict | list):
        return "'" + json.dumps(val, default=str).replace("'", "''") + "'::jsonb"
    s = str(val).replace("'", "''")
    return f"'{s}'"


def _insert(table: str, columns: list[str], row: tuple) -> str:
    """Build an INSERT INTO statement."""
    cols = ", ".join(columns)
    vals = ", ".join(_sql_val(v) for v in row)
    return f"INSERT INTO public.{table} ({cols}) VALUES ({vals});"


async def _get_descendant_uids(db: AsyncSession) -> list[str]:
    """Get all node UIDs under Special Projects (inclusive) in depth order."""
    result = await db.execute(text(
        "WITH RECURSIVE descendants AS ("
        "  SELECT node_uid FROM fc_node"
        "  WHERE title = :title AND parent_node_uid IS NULL"
        "  UNION ALL"
        "  SELECT n.node_uid FROM fc_node n"
        "  JOIN descendants d ON n.parent_node_uid = d.node_uid"
        ") SELECT node_uid FROM descendants"
    ), {"title": PLAYGROUND_ROOT_TITLE})
    return [str(r[0]) for r in result.all()]


async def _dump_users(db: AsyncSession) -> list[str]:
    """Dump playground-only user INSERT statements."""
    placeholders = ", ".join(f"'{u}'" for u in PLAYGROUND_USERNAMES)
    result = await db.execute(text(
        f"SELECT user_uid, cac_dn, edipi, display_name, email, "
        f"global_role, is_active, created_at, updated_at, last_login_at, password_hash "
        f"FROM fc_user WHERE cac_dn IN ({placeholders}) ORDER BY cac_dn"
    ))
    cols = [
        "user_uid", "cac_dn", "edipi", "display_name", "email",
        "global_role", "is_active", "created_at", "updated_at",
        "last_login_at", "password_hash",
    ]
    return [_insert("fc_user", cols, row) for row in result.all()]


async def _dump_table(
    db: AsyncSession,
    table: str,
    columns: list[str],
    where: str,
    order_by: str = "",
) -> list[str]:
    """Dump rows from a table matching the given WHERE clause."""
    cols_sql = ", ".join(columns)
    sql = f"SELECT {cols_sql} FROM {table} WHERE {where}"
    if order_by:
        sql += f" ORDER BY {order_by}"
    result = await db.execute(text(sql))
    return [_insert(table, columns, row) for row in result.all()]


async def _dump_fact_updates(db: AsyncSession, node_uids: list[str]) -> list[str]:
    """Dump UPDATE statements for fc_fact version pointers."""
    uid_list = ", ".join(f"'{u}'" for u in node_uids)
    result = await db.execute(text(
        f"SELECT fact_uid, current_published_version_uid, current_signed_version_uid "
        f"FROM fc_fact WHERE node_uid IN ({uid_list}) "
        f"AND (current_published_version_uid IS NOT NULL "
        f"OR current_signed_version_uid IS NOT NULL)"
    ))
    lines: list[str] = []
    for row in result.all():
        sets = []
        if row[1] is not None:
            sets.append(f"current_published_version_uid = '{row[1]}'")
        if row[2] is not None:
            sets.append(f"current_signed_version_uid = '{row[2]}'")
        if sets:
            lines.append(
                f"UPDATE public.fc_fact SET {', '.join(sets)} "
                f"WHERE fact_uid = '{row[0]}';"
            )
    return lines


async def generate() -> None:
    """Generate playground_snapshot.sql."""
    log.info("snapshot_generation_starting")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        node_uids = await _get_descendant_uids(db)
        if not node_uids:
            log.error("no_playground_nodes_found")
            await engine.dispose()
            return

        uid_list = ", ".join(f"'{u}'" for u in node_uids)
        lines: list[str] = [
            "-- Playground snapshot: Special Projects program data only",
            f"-- Generated from live database ({len(node_uids)} nodes)",
            "",
        ]

        # Users
        lines.append("-- Playground users")
        lines.extend(await _dump_users(db))
        lines.append("")

        # Nodes (depth order — parents before children)
        lines.append("-- Nodes (depth-ascending order)")
        node_cols = [
            "node_uid", "parent_node_uid", "title", "slug", "node_depth",
            "sort_order", "is_archived", "created_at", "updated_at", "created_by_uid",
        ]
        lines.extend(await _dump_table(
            db, "fc_node", node_cols,
            f"node_uid IN ({uid_list})", "node_depth, sort_order",
        ))
        lines.append("")

        # Node permissions
        lines.append("-- Node permissions")
        perm_cols = [
            "permission_uid", "user_uid", "node_uid", "role",
            "granted_by_uid", "created_at", "revoked_at",
        ]
        lines.extend(await _dump_table(
            db, "fc_node_permission", perm_cols,
            f"node_uid IN ({uid_list})",
        ))
        lines.append("")

        # Facts (without version pointers — set via UPDATE after versions)
        lines.append("-- Facts (version pointers set after version INSERTs)")
        fact_cols = [
            "fact_uid", "node_uid", "is_retired", "created_at",
            "created_by_uid", "retired_at", "retired_by_uid",
        ]
        lines.extend(await _dump_table(
            db, "fc_fact", fact_cols,
            f"node_uid IN ({uid_list})", "created_at",
        ))
        lines.append("")

        # Versions
        lines.append("-- Fact versions")
        ver_cols = [
            "version_uid", "fact_uid", "state", "display_sentence",
            "canonical_json", "metadata_tags", "source_reference",
            "effective_date", "last_verified_date", "classification",
            "applies_to", "change_summary", "supersedes_version_uid",
            "created_by_uid", "created_at", "published_at", "signed_at",
        ]
        fact_uid_subq = f"SELECT fact_uid FROM fc_fact WHERE node_uid IN ({uid_list})"
        lines.extend(await _dump_table(
            db, "fc_fact_version", ver_cols,
            f"fact_uid IN ({fact_uid_subq})", "created_at",
        ))
        lines.append("")

        # UPDATE fact pointers
        lines.append("-- Fact version pointer UPDATEs")
        lines.extend(await _dump_fact_updates(db, node_uids))
        lines.append("")

        # Comments
        lines.append("-- Comments")
        comment_cols = [
            "comment_uid", "version_uid", "parent_comment_uid", "comment_type",
            "body", "created_by_uid", "created_at", "resolved_at",
            "resolved_by_uid", "proposed_sentence", "resolution_state",
            "resolution_note",
        ]
        ver_subq = (
            f"SELECT version_uid FROM fc_fact_version "
            f"WHERE fact_uid IN ({fact_uid_subq})"
        )
        lines.extend(await _dump_table(
            db, "fc_fact_comment", comment_cols,
            f"version_uid IN ({ver_subq})", "created_at",
        ))
        lines.append("")

        # Signatures
        lines.append("-- Signatures")
        sig_cols = [
            "signature_uid", "node_uid", "signed_by_uid", "signed_at",
            "fact_count", "note", "expires_at",
        ]
        lines.extend(await _dump_table(
            db, "fc_signature", sig_cols,
            f"node_uid IN ({uid_list})",
        ))
        lines.append("")

        # Events (omit seq — GENERATED ALWAYS, DB assigns new values)
        lines.append("-- Events (seq omitted — DB assigns new values)")
        event_cols = [
            "event_uid", "entity_type", "entity_uid", "event_type",
            "payload", "actor_uid", "note", "occurred_at",
            "reversible", "reverse_payload",
        ]
        entity_uids_subq = (
            f"SELECT node_uid FROM fc_node WHERE node_uid IN ({uid_list}) "
            f"UNION ALL SELECT fact_uid FROM fc_fact WHERE node_uid IN ({uid_list}) "
            f"UNION ALL SELECT version_uid FROM fc_fact_version "
            f"WHERE fact_uid IN ({fact_uid_subq}) "
            f"UNION ALL SELECT comment_uid FROM fc_fact_comment "
            f"WHERE version_uid IN ({ver_subq}) "
            f"UNION ALL SELECT signature_uid FROM fc_signature "
            f"WHERE node_uid IN ({uid_list})"
        )
        lines.extend(await _dump_table(
            db, "fc_event_log", event_cols,
            f"entity_uid IN ({entity_uids_subq})", "occurred_at",
        ))
        lines.append("")

    await engine.dispose()

    output = "\n".join(lines) + "\n"
    # Try the project path first; fall back to /tmp if container FS is read-only
    for path in (OUTPUT_PATH, Path("/tmp/playground_snapshot.sql")):
        try:
            path.write_text(output, encoding="utf-8")
            log.info("snapshot_generated", path=str(path), lines=len(lines))
            return
        except PermissionError:
            continue
    log.error("snapshot_write_failed", tried=[str(OUTPUT_PATH), "/tmp"])


if __name__ == "__main__":
    asyncio.run(generate())
