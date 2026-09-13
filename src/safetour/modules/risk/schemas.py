"""Pydantic response models for the risk HTTP API."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from safetour.modules.risk.domain import RiskBand, TimeBand, UnitType


class RiskLookupResponse(BaseModel):
    unit_id: UUID | None
    unit_type: UnitType
    time_band: TimeBand
    score: float | None
    band: RiskBand
    data_date: str | None
    top_features: list[str]
    source: str


class HeatmapCellResponse(BaseModel):
    precinct_id: UUID
    score: float | None
    band: RiskBand
    data_date: str | None
