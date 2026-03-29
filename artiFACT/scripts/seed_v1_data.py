"""Seed v2 database with migrated v1 corpus data."""

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

from artiFACT.kernel.config import settings
from artiFACT.kernel.models import (
    Base,
    FcEventLog,
    FcFact,
    FcFactVersion,
    FcNode,
    FcNodePermission,
    FcUser,
)
from artiFACT.modules.auth_admin.service import hash_password

log = structlog.get_logger()

SQL_DUMP_PATH = Path("/app/docs/techstat_factcorpus.sql")

NODE_TYPE_DEPTH = {"trunk": 0, "branch": 1, "twig": 2, "leaf": 3, "vein": 4}

# v2 user definitions
JALLRED_UID = uuid.UUID("a0000001-0000-4000-8000-000000000001")
DWALLACE_UID = uuid.UUID("a0000002-0000-4000-8000-000000000002")
OMARTINEZ_UID = uuid.UUID("a0000003-0000-4000-8000-000000000003")
PBEESLY_UID = uuid.UUID("a0000004-0000-4000-8000-000000000004")

V2_USERS = [
    {
        "user_uid": JALLRED_UID,
        "cac_dn": "jallred",
        "display_name": "Jordan Allred",
        "global_role": "admin",
        "is_active": True,
        "password_hash": hash_password("playground2026"),
    },
    {
        "user_uid": DWALLACE_UID,
        "cac_dn": "dwallace",
        "display_name": "David Wallace",
        "global_role": "viewer",
        "is_active": True,
        "password_hash": hash_password("playground2026"),
    },
    {
        "user_uid": OMARTINEZ_UID,
        "cac_dn": "omartinez",
        "display_name": "Oscar Martinez",
        "global_role": "viewer",
        "is_active": True,
        "password_hash": hash_password("playground2026"),
    },
    {
        "user_uid": PBEESLY_UID,
        "cac_dn": "pbeesly",
        "display_name": "Pam Beesly",
        "global_role": "viewer",
        "is_active": True,
        "password_hash": hash_password("playground2026"),
    },
]

# Map old v1 user UIDs → v2 user UIDs
USER_UID_MAP: dict[str, uuid.UUID] = {
    "user-michael": JALLRED_UID,
    "user-wallace": DWALLACE_UID,
}


def _map_user_uid(old_uid: str | None) -> uuid.UUID | None:
    """Map a v1 user UID string to a v2 UUID."""
    if not old_uid or old_uid == "NULL":
        return None
    return USER_UID_MAP.get(old_uid, JALLRED_UID)


def _parse_datetime(val: str | None) -> datetime | None:
    """Parse v1 MySQL datetime string to timezone-aware UTC datetime."""
    if not val or val == "NULL":
        return None
    dt = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=timezone.utc)


def _parse_json(val: str | None) -> dict | list | None:
    """Parse JSON text, returning None for NULL/empty."""
    if not val or val == "NULL":
        return None
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return None


def _parse_uuid(val: str | None) -> uuid.UUID | None:
    """Parse a UUID string, returning None for NULL/empty."""
    if not val or val == "NULL":
        return None
    return uuid.UUID(val)


def _parse_bool(val: str | None) -> bool:
    """Parse a MySQL tinyint to boolean."""
    if not val or val == "NULL":
        return False
    return val.strip() not in ("0", "false", "False")


def _extract_rows(sql: str, table: str) -> list[list[str]]:
    """Extract INSERT row values for a given table from MySQL dump.

    Returns a list of rows, where each row is a list of raw string values.
    """
    pattern = (
        rf"INSERT INTO `{table}` \(`[^)]+`\) VALUES\s*\n"
    )
    rows: list[list[str]] = []

    blocks = list(re.finditer(pattern, sql))
    if not blocks:
        log.warning("no_insert_blocks", table=table)
        return rows

    for block in blocks:
        start = block.end()
        end = sql.find(";\n", start)
        if end == -1:
            end = len(sql)
        values_text = sql[start:end]
        rows.extend(_parse_values_block(values_text))

    log.info("extracted_rows", table=table, count=len(rows))
    return rows


def _parse_values_block(text: str) -> list[list[str]]:
    """Parse MySQL VALUES block into list of row value lists.

    Handles escaped quotes, NULL values, and nested parentheses.
    """
    rows: list[list[str]] = []
    i = 0
    length = len(text)

    while i < length:
        if text[i] == "(":
            values, end_pos = _parse_single_row(text, i)
            rows.append(values)
            i = end_pos
        else:
            i += 1

    return rows


def _parse_single_row(text: str, start: int) -> tuple[list[str], int]:
    """Parse a single parenthesized row of values starting at position start."""
    values: list[str] = []
    i = start + 1  # skip opening paren
    length = len(text)

    while i < length:
        # Skip whitespace
        while i < length and text[i] in (" ", "\t", "\n"):
            i += 1

        if i >= length:
            break

        if text[i] == ")":
            return values, i + 1

        if text[i] == ",":
            i += 1
            continue

        if text[i] == "'":
            # Quoted string value
            val, end = _parse_quoted_string(text, i)
            values.append(val)
            i = end
        elif text[i:i + 4].upper() == "NULL":
            values.append("NULL")
            i += 4
        else:
            # Unquoted value (number, etc.)
            end = i
            while end < length and text[end] not in (",", ")"):
                end += 1
            values.append(text[i:end].strip())
            i = end

    return values, i


def _parse_quoted_string(text: str, start: int) -> tuple[str, int]:
    """Parse a single-quoted MySQL string starting at position start.

    Handles escaped quotes (\' and '') and backslash escapes.
    """
    result: list[str] = []
    i = start + 1  # skip opening quote
    length = len(text)

    while i < length:
        ch = text[i]
        if ch == "\\" and i + 1 < length:
            next_ch = text[i + 1]
            if next_ch == "'":
                result.append("'")
                i += 2
            elif next_ch == "\\":
                result.append("\\")
                i += 2
            elif next_ch == "n":
                result.append("\n")
                i += 2
            else:
                result.append(next_ch)
                i += 2
        elif ch == "'" and i + 1 < length and text[i + 1] == "'":
            result.append("'")
            i += 2
        elif ch == "'":
            return "".join(result), i + 1
        else:
            result.append(ch)
            i += 1

    return "".join(result), i


async def _seed_users(db: AsyncSession) -> None:
    """Insert v2 playground users if not already present."""
    for user_data in V2_USERS:
        existing = await db.get(FcUser, user_data["user_uid"])
        if existing:
            log.info("user_exists", username=user_data["cac_dn"])
            continue
        user = FcUser(**user_data)
        db.add(user)
        log.info("user_created", username=user_data["cac_dn"])
    await db.flush()


async def _seed_nodes(db: AsyncSession, sql: str) -> None:
    """Parse and insert v1 nodes into v2 schema.

    Uses topological sort to insert parents before children, and computes
    actual depth from the parent chain (v1 node_type doesn't map cleanly).
    """
    rows = _extract_rows(sql, "fc_node")
    # Column order: node_uid, parent_node_uid, node_type, title, slug,
    #               sort_order, owner_scope_uid, created_at_utc, updated_at_utc

    # Build lookup and compute actual depth from parent chain
    row_by_uid: dict[str, list[str]] = {}
    for row in rows:
        row_by_uid[row[0]] = row

    def _compute_depth(uid: str) -> int:
        depth = 0
        current = uid
        for _ in range(20):  # safety limit
            r = row_by_uid.get(current)
            if not r or r[1] == "NULL":
                break
            current = r[1]
            depth += 1
        return depth

    depth_map: dict[str, int] = {uid: _compute_depth(uid) for uid in row_by_uid}

    # Topological sort: order by computed depth
    rows.sort(key=lambda r: depth_map.get(r[0], 0))

    # Check existing node UIDs upfront to avoid autoflush issues
    existing_result = await db.execute(
        text("SELECT node_uid FROM fc_node")
    )
    existing_uids = {row[0] for row in existing_result.fetchall()}

    inserted = 0
    current_depth = -1
    for row in rows:
        node_uid = _parse_uuid(row[0])
        if not node_uid or node_uid in existing_uids:
            continue

        depth = depth_map.get(row[0], 0)

        # Flush between depth levels to satisfy FK ordering
        if depth != current_depth and current_depth >= 0:
            await db.flush()
        current_depth = depth

        node = FcNode(
            node_uid=node_uid,
            parent_node_uid=_parse_uuid(row[1]),
            title=row[3],
            slug=row[4],
            node_depth=depth,
            sort_order=int(row[5]),
            is_archived=False,
            created_at=_parse_datetime(row[7]),
            updated_at=_parse_datetime(row[8]),
            created_by_uid=JALLRED_UID,
        )
        db.add(node)
        inserted += 1

    await db.flush()
    log.info("nodes_seeded", inserted=inserted, total=len(rows))


async def _seed_facts(db: AsyncSession, sql: str) -> None:
    """Parse and insert v1 facts into v2 schema (without version pointers)."""
    rows = _extract_rows(sql, "fc_fact")
    # Column order: fact_uid, node_uid, fact_family_uid,
    #               current_signed_version_uid, current_published_version_uid,
    #               is_retired, created_at_utc, created_by_user_uid

    existing_result = await db.execute(text("SELECT fact_uid FROM fc_fact"))
    existing_uids = {row[0] for row in existing_result.fetchall()}

    inserted = 0
    for row in rows:
        fact_uid = _parse_uuid(row[0])
        if not fact_uid or fact_uid in existing_uids:
            continue

        fact = FcFact(
            fact_uid=fact_uid,
            node_uid=_parse_uuid(row[1]),
            current_signed_version_uid=None,
            current_published_version_uid=None,
            is_retired=_parse_bool(row[5]),
            created_at=_parse_datetime(row[6]),
            created_by_uid=_map_user_uid(row[7]),
        )
        db.add(fact)
        inserted += 1

    await db.flush()
    log.info("facts_seeded", inserted=inserted, total=len(rows))


async def _seed_versions(db: AsyncSession, sql: str) -> None:
    """Parse and insert v1 fact versions into v2 schema."""
    rows = _extract_rows(sql, "fc_fact_version")
    # Column order: version_uid, fact_uid, state, display_sentence_good,
    #               canonical_json, metadata_tags_json, source_reference_json,
    #               effective_date, last_verified_date, classification,
    #               applies_to, created_at_utc, created_by_user_uid,
    #               supersedes_version_uid, change_summary,
    #               signed_at_utc, published_at_utc

    existing_result = await db.execute(text("SELECT version_uid FROM fc_fact_version"))
    existing_uids = {row[0] for row in existing_result.fetchall()}

    inserted = 0
    for row in rows:
        version_uid = _parse_uuid(row[0])
        if not version_uid or version_uid in existing_uids:
            continue

        state = row[2]
        created_at = _parse_datetime(row[11])
        published_at = _parse_datetime(row[16])

        # Fix S-BUG-01: published versions with NULL published_at
        if state == "published" and published_at is None and created_at:
            published_at = created_at

        effective_date_raw = row[7] if row[7] != "NULL" else None
        last_verified_raw = row[8] if row[8] != "NULL" else None
        classification = row[9] if row[9] != "NULL" else "UNCLASSIFIED"

        metadata_tags = _parse_json(row[5])
        if metadata_tags is None:
            metadata_tags = []

        version = FcFactVersion(
            version_uid=version_uid,
            fact_uid=_parse_uuid(row[1]),
            state=state,
            display_sentence=row[3],
            canonical_json=_parse_json(row[4]),
            metadata_tags=metadata_tags,
            source_reference=_parse_json(row[6]),
            effective_date=effective_date_raw,
            last_verified_date=last_verified_raw,
            classification=classification or "UNCLASSIFIED",
            applies_to=row[10] if row[10] != "NULL" else None,
            created_at=created_at,
            created_by_uid=_map_user_uid(row[12]),
            supersedes_version_uid=None,  # deferred to avoid self-ref FK
            change_summary=row[14] if row[14] != "NULL" else None,
            signed_at=_parse_datetime(row[15]),
            published_at=published_at,
        )
        db.add(version)
        inserted += 1

    await db.flush()

    # Second pass: set supersedes_version_uid
    supersedes_count = 0
    for row in rows:
        supersedes_uid = _parse_uuid(row[13])
        if not supersedes_uid:
            continue
        version_uid = _parse_uuid(row[0])
        if version_uid and version_uid not in existing_uids:
            await db.execute(
                text(
                    "UPDATE fc_fact_version SET supersedes_version_uid = :sup "
                    "WHERE version_uid = :vid"
                ),
                {"sup": supersedes_uid, "vid": version_uid},
            )
            supersedes_count += 1

    await db.flush()
    log.info("versions_seeded", inserted=inserted, supersedes=supersedes_count)


async def _update_fact_version_pointers(db: AsyncSession, sql: str) -> None:
    """Set current_published_version_uid and current_signed_version_uid on facts."""
    rows = _extract_rows(sql, "fc_fact")
    updated = 0
    for row in rows:
        fact_uid = _parse_uuid(row[0])
        pub_uid = _parse_uuid(row[4])
        signed_uid = _parse_uuid(row[3])

        if not fact_uid or (not pub_uid and not signed_uid):
            continue

        fact = await db.get(FcFact, fact_uid)
        if not fact:
            continue

        changed = False
        if pub_uid and fact.current_published_version_uid != pub_uid:
            fact.current_published_version_uid = pub_uid
            changed = True
        if signed_uid and fact.current_signed_version_uid != signed_uid:
            fact.current_signed_version_uid = signed_uid
            changed = True

        if changed:
            updated += 1

    await db.flush()
    log.info("fact_pointers_updated", updated=updated)


async def _seed_permissions(db: AsyncSession) -> None:
    """Create node permissions for playground users."""
    # Find key node UIDs
    root_result = await db.execute(
        select(FcNode).where(FcNode.parent_node_uid.is_(None))
    )
    root = root_result.scalar_one_or_none()
    if not root:
        log.error("root_node_not_found")
        return

    boatwing_result = await db.execute(
        select(FcNode).where(FcNode.title == "Boatwing H-12")
    )
    boatwing = boatwing_result.scalar_one_or_none()

    snipeb_result = await db.execute(
        select(FcNode).where(FcNode.title == "SNIPE-B")
    )
    snipeb = snipeb_result.scalar_one_or_none()

    if not boatwing or not snipeb:
        log.error("program_nodes_not_found")
        return

    permissions = [
        (DWALLACE_UID, root.node_uid, "signatory"),
        (OMARTINEZ_UID, boatwing.node_uid, "approver"),
        (OMARTINEZ_UID, snipeb.node_uid, "approver"),
        (PBEESLY_UID, boatwing.node_uid, "contributor"),
        (PBEESLY_UID, snipeb.node_uid, "contributor"),
    ]

    inserted = 0
    for user_uid, node_uid, role in permissions:
        existing = await db.execute(
            select(FcNodePermission).where(
                FcNodePermission.user_uid == user_uid,
                FcNodePermission.node_uid == node_uid,
                FcNodePermission.revoked_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            continue

        perm = FcNodePermission(
            permission_uid=uuid.uuid4(),
            user_uid=user_uid,
            node_uid=node_uid,
            role=role,
            granted_by_uid=JALLRED_UID,
        )
        db.add(perm)
        inserted += 1

    await db.flush()
    log.info("permissions_seeded", inserted=inserted)


async def _seed_events(db: AsyncSession) -> None:
    """Generate event log entries from version data."""
    result = await db.execute(select(FcFactVersion))
    versions = result.scalars().all()

    # Check if events already exist
    event_count = await db.execute(
        text("SELECT COUNT(*) FROM fc_event_log")
    )
    if event_count.scalar() > 0:
        log.info("events_already_exist")
        return

    created = 0
    for ver in versions:
        # Every version gets a proposed event
        proposed_event = FcEventLog(
            event_uid=uuid.uuid4(),
            entity_type="version",
            entity_uid=ver.version_uid,
            event_type="fact.proposed",
            payload={"state": "proposed", "fact_uid": str(ver.fact_uid)},
            actor_uid=ver.created_by_uid,
            occurred_at=ver.created_at,
        )
        db.add(proposed_event)
        created += 1

        if ver.state == "published":
            pub_at = ver.published_at or (
                ver.created_at + timedelta(minutes=1)
                if ver.created_at
                else None
            )
            pub_event = FcEventLog(
                event_uid=uuid.uuid4(),
                entity_type="version",
                entity_uid=ver.version_uid,
                event_type="fact.published",
                payload={"state": "published", "fact_uid": str(ver.fact_uid)},
                actor_uid=ver.created_by_uid,
                occurred_at=pub_at,
            )
            db.add(pub_event)
            created += 1

        elif ver.state == "rejected":
            rej_at = ver.created_at + timedelta(minutes=1) if ver.created_at else None
            rej_event = FcEventLog(
                event_uid=uuid.uuid4(),
                entity_type="version",
                entity_uid=ver.version_uid,
                event_type="fact.rejected",
                payload={"state": "rejected", "fact_uid": str(ver.fact_uid)},
                actor_uid=ver.created_by_uid,
                occurred_at=rej_at,
            )
            db.add(rej_event)
            created += 1

    await db.flush()
    log.info("events_seeded", created=created)


async def run_seed() -> None:
    """Main seed entry point."""
    log.info("seed_starting")

    if not SQL_DUMP_PATH.exists():
        log.error("sql_dump_not_found", path=str(SQL_DUMP_PATH))
        raise FileNotFoundError(f"SQL dump not found: {SQL_DUMP_PATH}")

    sql = SQL_DUMP_PATH.read_text(encoding="utf-8")
    log.info("sql_dump_loaded", size_bytes=len(sql))

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as db:
        async with db.begin():
            await _seed_users(db)
            await _seed_nodes(db, sql)
            await _seed_facts(db, sql)
            await _seed_versions(db, sql)
            await _update_fact_version_pointers(db, sql)
            await _seed_permissions(db)
            await _seed_events(db)

    await engine.dispose()
    log.info("seed_complete")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_seed())
