"""Pydantic request/response models for the routing HTTP API (FR-ROUTE-*)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from safetour.modules.risk.domain import RiskBand, TimeBand


class RoutePlanRequest(BaseModel):
    origin_lon: float = Field(ge=-180, le=180)
    origin_lat: float = Field(ge=-90, le=90)
    destination_lon: float = Field(ge=-180, le=180)
    destination_lat: float = Field(ge=-90, le=90)
    mode: str = "walking"
    time_band: TimeBand | None = None


class RouteLegResponse(BaseModel):
    start_lon: float
    start_lat: float
    end_lon: float
    end_lat: float
    mode: str
    distance_m: float
    duration_s: float
    risk_band: RiskBand
    is_flagged_high_risk: bool


class RouteOptionResponse(BaseModel):
    label: str
    legs: list[RouteLegResponse]
    total_distance_m: float
    total_duration_s: float
    overall_risk_band: RiskBand
    rationale: str
