"""
Geo domain: the spatial reference data shared across modules.

Precincts and segments are "the spatial anchors that tie crime data, context,
risk scores, attractions and routes together" (section 25) — every other
module that needs a place resolves it through here rather than owning its
own copy of the geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry


class AttractionCategory(StrEnum):
    ATTRACTION = "attraction"
    TAXI_RANK = "taxi_rank"
    BUS_STOP = "bus_stop"
    RAIL_STATION = "rail_station"
    SAFE_POINT = "safe_point"
    POLICE_STATION = "police_station"
    MARKET = "market"
    OTHER = "other"

    @property
    def is_transport_stop(self) -> bool:
        return self in {
            AttractionCategory.TAXI_RANK,
            AttractionCategory.BUS_STOP,
            AttractionCategory.RAIL_STATION,
        }


@dataclass(slots=True)
class Precinct:
    id: UUID
    name: str
    boundary: BaseGeometry
    population: int | None = None


@dataclass(slots=True)
class Segment:
    id: UUID
    precinct_id: UUID
    geometry: LineString
    modes: list[str]


@dataclass(slots=True)
class AttractionStop:
    id: UUID
    name: str
    category: AttractionCategory
    location: Point
    precinct_id: UUID | None
    opening_hours: dict[str, Any] | None = None


class GeoReadRepository(Protocol):
    async def get_precinct(self, precinct_id: UUID) -> Precinct | None: ...
    async def list_precincts(self) -> list[Precinct]: ...
    async def find_precinct_for_point(self, lon: float, lat: float) -> Precinct | None: ...
    async def find_nearest_segment(self, lon: float, lat: float, *, mode: str | None = None) -> Segment | None: ...
    async def list_segments_in_precinct(self, precinct_id: UUID) -> list[Segment]: ...
    async def list_all_segments(self, *, mode: str | None = None) -> list[Segment]: ...
    async def list_attractions(
        self,
        *,
        precinct_id: UUID | None = None,
        category: AttractionCategory | None = None,
        near: tuple[float, float] | None = None,
        radius_m: float = 2000.0,
        limit: int = 50,
    ) -> list[AttractionStop]: ...
    async def get_attraction(self, attraction_id: UUID) -> AttractionStop | None: ...
