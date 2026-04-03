"""Seed fc_acronym from the base acronyms CSV."""

import csv
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcAcronym

log = structlog.get_logger()

_CSV_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "acronyms_seed.csv"


async def seed_acronyms(db: AsyncSession) -> int:
    """Insert acronyms from seed CSV. Skip duplicates. Returns count of inserted rows."""
    if not _CSV_PATH.exists():
        log.warning("acronym.seed_csv_missing", path=str(_CSV_PATH))
        return 0

    existing_result = await db.execute(
        select(FcAcronym.acronym, FcAcronym.spelled_out)
    )
    existing_set: set[tuple[str, str]] = {
        (r.acronym.strip().upper(), (r.spelled_out or "").strip().upper())
        for r in existing_result.all()
    }

    inserted = 0
    with open(_CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header

        for row in reader:
            if len(row) < 2:
                continue
            acronym = row[0].strip()[:50]
            spelled_out = row[1].strip()[:200]

            if not acronym:
                continue

            key = (acronym.upper(), spelled_out.upper())
            if key in existing_set:
                continue

            db.add(FcAcronym(
                acronym=acronym,
                spelled_out=spelled_out if spelled_out else None,
            ))
            existing_set.add(key)
            inserted += 1

    await db.flush()
    log.info("acronym.seeded", inserted=inserted)
    return inserted
