"""
Routing domain — stateless: route options are computed on request and only
persisted if a user explicitly saves one as (or into) an itinerary, which is
the ``itineraries`` module's job (section 25: "Itinerary and route" is one
persisted entity, owned there).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from safetour.modules.risk.domain import RiskBand

_MODE_SPEEDS_KMH = {
    "walking": 5.0,
    "minibus_taxi": 25.0,
    "bus_rapid_transit": 20.0,
    "rail": 35.0,
    "e_hailing": 30.0,
}

DEFAULT_MODE = "walking"


@dataclass(slots=True)
class LonLat:
    lon: float
    lat: float


@dataclass(slots=True)
class RouteLeg:
    start: LonLat
    end: LonLat
    mode: str
    distance_m: float
    duration_s: float
    risk_band: RiskBand
    is_flagged_high_risk: bool
    segment_id: UUID | None = None


@dataclass(slots=True)
class RouteOption:
    label: str  # "fastest" | "lower_risk"
    legs: list[RouteLeg]
    total_distance_m: float
    total_duration_s: float
    overall_risk_band: RiskBand
    rationale: str


def speed_kmh_for_mode(mode: str) -> float:
    return _MODE_SPEEDS_KMH.get(mode, _MODE_SPEEDS_KMH[DEFAULT_MODE])
