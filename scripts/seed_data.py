"""
Seed a small, self-consistent demo dataset for the Tshwane pilot area
(section 29's "documented prototype", section 2's pilot-area target).

Precinct names, boundaries and populations are illustrative approximations
of real Pretoria neighbourhoods for demo purposes — NOT sourced from SAPS or
StatsSA and must not be presented as authoritative. Crime statistics are
synthetic, generated with a fixed random seed so re-running this script is
reproducible, with a deliberate pattern (the inner-city precincts trend
higher and rising, the residential ones lower and flatter) so the risk
model training script (train_and_score_risk_model.py) has a genuine,
learnable signal instead of pure noise.

Idempotent: if "Pretoria Central" already exists, the script exits without
writing anything (pass --force to wipe and reseed).

Usage:
    uv run python scripts/seed_data.py [--force]
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).parent))

from safetour.modules.auth.models import AuthAccountModel  # noqa: E402
from safetour.modules.geo.domain import AttractionCategory  # noqa: E402
from safetour.modules.geo.models import (  # noqa: E402
    AttractionStopModel,
    PrecinctModel,
    SegmentModel,
    shape_to_geometry,
)
from safetour.modules.risk.models import CrimeStatisticModel  # noqa: E402
from safetour.modules.users.domain import Persona  # noqa: E402
from safetour.modules.users.models import ProfileModel  # noqa: E402
from safetour.shared.database import AsyncSessionLocal  # noqa: E402
from safetour.shared.security import hash_password  # noqa: E402

_SEED = 42
_ADMIN_EMAIL = "admin@safetour.co.za"  # pydantic's EmailStr rejects reserved TLDs like .local
_ADMIN_PASSWORD = "ChangeMe1234!"  # demo-only credential — rotate before any shared deployment
_QUARTERS = ["2024Q1", "2024Q2", "2024Q3", "2024Q4"]
_CATEGORIES = ["contact_crime", "property_crime"]


@dataclass(slots=True)
class PrecinctSeed:
    name: str
    lon: float
    lat: float
    population: int
    base_rate: float  # starting rate_per_100k for contact_crime in 2024Q1
    trend_per_quarter: float  # additive change per quarter (can be negative)


# Approximate centres of real Pretoria/Tshwane neighbourhoods — illustrative
# only. With just 5 precincts the trained model's predictions split cleanly
# into a "high" group {Pretoria Central, Sunnyside} and a "low" group
# {Arcadia, Hatfield, Brooklyn} — so the bias check's correlation is really
# driven by whether those two groups have the same *average* population, not
# by each value individually. Both groups average ~14000 here on purpose, so
# the demo can also exercise a passing bias audit / promoted model, not only
# the (equally real, previously observed) blocked-promotion path.
_PRECINCTS = [
    PrecinctSeed("Pretoria Central", 28.1881, -25.7461, 13000, 620.0, 35.0),
    PrecinctSeed("Sunnyside", 28.2100, -25.7550, 15000, 540.0, 28.0),
    PrecinctSeed("Arcadia", 28.2107, -25.7418, 12000, 210.0, -8.0),
    PrecinctSeed("Hatfield", 28.2378, -25.7545, 16000, 190.0, -5.0),
    PrecinctSeed("Brooklyn", 28.2350, -25.7580, 14000, 150.0, -10.0),
]

_BOX_DEGREES = 0.006  # ~650m half-width demo precinct "boundary"


def _box_polygon(lon: float, lat: float) -> MultiPolygon:
    d = _BOX_DEGREES
    ring = Polygon([(lon - d, lat - d), (lon + d, lat - d), (lon + d, lat + d), (lon - d, lat + d), (lon - d, lat - d)])
    return MultiPolygon([ring])


async def _already_seeded(session) -> bool:
    result = await session.execute(select(PrecinctModel).where(PrecinctModel.name == "Pretoria Central"))
    return result.scalar_one_or_none() is not None


async def _wipe(session) -> None:
    for model in (CrimeStatisticModel, AttractionStopModel, SegmentModel, PrecinctModel):
        await session.execute(delete(model))


async def _seed_precincts(session) -> dict[str, UUID]:
    ids: dict[str, UUID] = {}
    for seed in _PRECINCTS:
        precinct_id = uuid4()
        ids[seed.name] = precinct_id
        session.add(
            PrecinctModel(
                id=precinct_id, name=seed.name, population=seed.population,
                boundary=shape_to_geometry(_box_polygon(seed.lon, seed.lat)),
            )
        )
    await session.flush()
    return ids


def _rate_for_quarter(seed: PrecinctSeed, quarter_index: int, category: str, rng: random.Random) -> float:
    base = seed.base_rate if category == "contact_crime" else seed.base_rate * 0.6
    trend = seed.trend_per_quarter if category == "contact_crime" else seed.trend_per_quarter * 0.5
    noise = rng.uniform(-15.0, 15.0)
    return max(base + trend * quarter_index + noise, 5.0)


async def _seed_crime_statistics(session, precinct_ids: dict[str, UUID]) -> None:
    rng = random.Random(_SEED)
    for seed in _PRECINCTS:
        precinct_id = precinct_ids[seed.name]
        for quarter_index, period in enumerate(_QUARTERS):
            for category in _CATEGORIES:
                rate = _rate_for_quarter(seed, quarter_index, category, rng)
                count = round(rate / 100_000 * seed.population)
                session.add(
                    CrimeStatisticModel(
                        id=uuid4(), precinct_id=precinct_id, category=category, period=period,
                        count=count, rate_per_100k=rate,
                    )
                )


async def _seed_segments(session, precinct_ids: dict[str, UUID]) -> None:
    by_name = {seed.name: seed for seed in _PRECINCTS}

    def point_of(name: str) -> tuple[float, float]:
        s = by_name[name]
        return (s.lon, s.lat)

    # A loop through all five precincts plus one diagonal shortcut, so a
    # route between two precincts sometimes has a real lower-risk detour to
    # choose from rather than a single forced path.
    edges = [
        ("Pretoria Central", "Arcadia", ["walking", "minibus_taxi", "bus_rapid_transit"]),
        ("Arcadia", "Hatfield", ["walking", "minibus_taxi"]),
        ("Hatfield", "Brooklyn", ["walking", "minibus_taxi"]),
        ("Brooklyn", "Sunnyside", ["walking", "minibus_taxi"]),
        ("Sunnyside", "Pretoria Central", ["walking", "minibus_taxi", "bus_rapid_transit"]),
        ("Arcadia", "Sunnyside", ["walking", "minibus_taxi"]),  # diagonal shortcut/detour
    ]
    for from_name, to_name, modes in edges:
        line = LineString([point_of(from_name), point_of(to_name)])
        session.add(
            SegmentModel(
                id=uuid4(), precinct_id=precinct_ids[from_name], modes=modes, geometry=shape_to_geometry(line)
            )
        )


async def _seed_attractions(session, precinct_ids: dict[str, UUID]) -> None:
    by_name = {seed.name: seed for seed in _PRECINCTS}

    def near(name: str, dlon: float, dlat: float) -> Point:
        s = by_name[name]
        return Point(s.lon + dlon, s.lat + dlat)

    attractions = [
        ("Pretoria Central Taxi Rank", AttractionCategory.TAXI_RANK, "Pretoria Central", 0.001, -0.001),
        ("Sunnyside Taxi Rank", AttractionCategory.TAXI_RANK, "Sunnyside", -0.001, 0.001),
        ("Hatfield Gautrain Bus Stop", AttractionCategory.BUS_STOP, "Hatfield", 0.001, 0.001),
        ("Brooklyn Police Station", AttractionCategory.POLICE_STATION, "Brooklyn", -0.001, -0.001),
        ("Arcadia Police Station", AttractionCategory.POLICE_STATION, "Arcadia", 0.001, 0.0),
        ("Sunnyside Community Safe Point", AttractionCategory.SAFE_POINT, "Sunnyside", 0.001, -0.001),
        ("Church Square", AttractionCategory.ATTRACTION, "Pretoria Central", -0.002, 0.001),
        ("Hatfield Square", AttractionCategory.MARKET, "Hatfield", -0.001, -0.001),
        ("Brooklyn Mall", AttractionCategory.MARKET, "Brooklyn", 0.002, 0.001),
        ("Burgers Park", AttractionCategory.ATTRACTION, "Arcadia", -0.002, -0.001),
    ]
    for name, category, precinct_name, dlon, dlat in attractions:
        session.add(
            AttractionStopModel(
                id=uuid4(), name=name, category=category.value, precinct_id=precinct_ids[precinct_name],
                location=shape_to_geometry(near(precinct_name, dlon, dlat)),
            )
        )


async def _seed_admin_account(session) -> None:
    result = await session.execute(select(AuthAccountModel).where(AuthAccountModel.email == _ADMIN_EMAIL))
    if result.scalar_one_or_none() is not None:
        return
    account_id = uuid4()
    session.add(
        AuthAccountModel(
            id=account_id, email=_ADMIN_EMAIL, hashed_password=hash_password(_ADMIN_PASSWORD),
            is_admin=True, is_active=True, consented_at=datetime.now(UTC),
        )
    )
    session.add(
        ProfileModel(user_id=account_id, persona=Persona.ADMINISTRATOR.value, interests=[], transport_modes=["walking"])
    )


async def main(force: bool) -> None:
    async with AsyncSessionLocal() as session:
        if await _already_seeded(session) and not force:
            print("Seed data already present (found 'Pretoria Central') — pass --force to wipe and reseed.")
            return
        if force:
            await _wipe(session)

        precinct_ids = await _seed_precincts(session)
        await _seed_segments(session, precinct_ids)
        await _seed_attractions(session, precinct_ids)
        await _seed_crime_statistics(session, precinct_ids)
        await _seed_admin_account(session)
        await session.commit()

    print(f"Seeded {len(_PRECINCTS)} precincts, crime stats for {_QUARTERS}, segments, attractions.")
    print(f"Admin login: {_ADMIN_EMAIL} / {_ADMIN_PASSWORD} (demo only — rotate before sharing this deployment).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Wipe existing seed data first")
    args = parser.parse_args()
    asyncio.run(main(args.force))
