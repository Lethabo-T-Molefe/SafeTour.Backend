"""Pydantic response models for the geo reference API. Geometry is simplified
to lon/lat (points) or a coordinate ring (polygons) — enough for the Leaflet
client without pulling a full GeoJSON dependency into the API layer."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from safetour.modules.geo.domain import AttractionCategory


class PrecinctResponse(BaseModel):
    id: UUID
    name: str
    population: int | None
    boundary_geojson: dict[str, Any]


class AttractionResponse(BaseModel):
    id: UUID
    name: str
    category: AttractionCategory
    is_transport_stop: bool
    lon: float
    lat: float
    precinct_id: UUID | None
    opening_hours: dict[str, Any] | None
