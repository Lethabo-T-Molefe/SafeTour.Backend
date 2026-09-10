"""Pydantic request/response models for the itineraries HTTP API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from safetour.modules.itineraries.domain import ItineraryStatus
from safetour.modules.risk.domain import TimeBand


class ItineraryGenerateRequest(BaseModel):
    precinct_id: UUID | None = None
    interests: list[str] | None = None
    time_band: TimeBand | None = None


class ItineraryStopResponse(BaseModel):
    attraction_id: UUID
    order_index: int
    risk_band: str
    data_date: str | None
    rationale: str


class ItineraryResponse(BaseModel):
    id: UUID
    user_id: UUID
    precinct_id: UUID | None
    status: ItineraryStatus
    stops: list[ItineraryStopResponse]
    created_at: datetime
    updated_at: datetime
