"""
SAPS quarterly crime-statistics loader (FR-ADM-1: a validated, idempotent
quarterly loader).

SAPS publishes crime statistics quarterly at police-precinct level. This
script expects that release already reduced to a plain CSV with columns:

    precinct_name,category,count

Population is not repeated per row — it is read from the ``precincts`` table
(a stable attribute maintained separately, not something SAPS republishes
every quarter), and used to compute ``rate_per_100k`` here so risk scoring
always works from normalised rates, never raw counts (NFR-ETH-2).

Every row is validated (precinct name resolves, count is non-negative)
before anything is written; ingestion then goes through the same
``AdminService.ingest_crime_statistics`` the HTTP ``/admin/ingest`` endpoint
uses, which upserts on (precinct_id, category, period) — so re-running this
script for a period already loaded is a no-op update, not a duplicate load.

Usage:
    uv run python scripts/ingest_saps_csv.py data/2025q4.csv --period 2025Q4 --actor-email admin@example.com
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent))
from _composition import build_admin_service  # noqa: E402

from safetour.modules.admin.domain import InvalidIngestRowError  # noqa: E402
from safetour.modules.admin.service import IngestRow  # noqa: E402
from safetour.modules.auth.models import AuthAccountModel  # noqa: E402
from safetour.modules.geo.models import PrecinctModel  # noqa: E402
from safetour.shared.database import AsyncSessionLocal  # noqa: E402


class CsvValidationError(Exception):
    pass


async def _resolve_actor_id(session, actor_email: str | None) -> UUID:
    query = select(AuthAccountModel).where(AuthAccountModel.is_admin.is_(True))
    if actor_email:
        query = query.where(AuthAccountModel.email == actor_email.strip().lower())
    result = await session.execute(query.limit(1))
    account = result.scalar_one_or_none()
    if account is None:
        raise CsvValidationError(
            f"No admin account found{f' for {actor_email}' if actor_email else ''}. "
            "Register one and set is_admin=true first."
        )
    return account.id


async def _load_precinct_lookup(session) -> dict[str, tuple[UUID, int | None]]:
    result = await session.execute(select(PrecinctModel))
    return {row.name.strip().lower(): (row.id, row.population) for row in result.scalars().all()}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = {"precinct_name", "category", "count"} - set(reader.fieldnames or [])
        if missing:
            raise CsvValidationError(f"CSV is missing required columns: {', '.join(sorted(missing))}")
        return list(reader)


def _validate_and_build_rows(
    raw_rows: list[dict[str, str]], precinct_lookup: dict[str, tuple[UUID, int | None]]
) -> list[IngestRow]:
    errors: list[str] = []
    rows: list[IngestRow] = []

    for line_no, raw in enumerate(raw_rows, start=2):  # header is line 1
        name = raw["precinct_name"].strip()
        category = raw["category"].strip()
        count_text = raw["count"].strip()

        precinct = precinct_lookup.get(name.lower())
        if precinct is None:
            errors.append(f"line {line_no}: unknown precinct '{name}'")
            continue
        precinct_id, population = precinct

        try:
            count = int(count_text)
        except ValueError:
            errors.append(f"line {line_no}: count '{count_text}' is not an integer")
            continue
        if count < 0:
            errors.append(f"line {line_no}: count {count} is negative")
            continue
        if not population or population <= 0:
            errors.append(f"line {line_no}: precinct '{name}' has no population on record — cannot compute a rate")
            continue

        rate_per_100k = count / population * 100_000
        rows.append(IngestRow(precinct_id=precinct_id, category=category, count=count, rate_per_100k=rate_per_100k))

    if errors:
        raise CsvValidationError("Validation failed:\n  " + "\n  ".join(errors))
    return rows


async def main(csv_path: Path, period: str, actor_email: str | None) -> None:
    raw_rows = _read_csv(csv_path)
    if not raw_rows:
        print("CSV has no data rows — nothing to do.")
        return

    async with AsyncSessionLocal() as session:
        try:
            actor_id = await _resolve_actor_id(session, actor_email)
            precinct_lookup = await _load_precinct_lookup(session)
            rows = _validate_and_build_rows(raw_rows, precinct_lookup)

            admin_service = build_admin_service(session)
            count = await admin_service.ingest_crime_statistics(actor_id, period, rows)
            await session.commit()
            print(f"Ingested {count} rows for period {period}.")
        except (CsvValidationError, InvalidIngestRowError) as exc:
            await session.rollback()
            print(f"Ingestion aborted — nothing was written.\n{exc}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--period", required=True, help='e.g. "2025Q4"')
    parser.add_argument("--actor-email", default=None, help="Admin account to attribute the ingest to in the audit log")
    args = parser.parse_args()
    asyncio.run(main(args.csv_path, args.period, args.actor_email))
