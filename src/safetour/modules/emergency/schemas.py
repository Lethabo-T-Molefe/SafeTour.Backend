"""Pydantic request/response models for the emergency HTTP API (FR-EMG-*)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from safetour.modules.emergency.domain import ShareChannel, TripStatus


class StartTripRequest(BaseModel):
    origin_lon: float = Field(ge=-180, le=180)
    origin_lat: float = Field(ge=-90, le=90)
    destination_lon: float = Field(ge=-180, le=180)
    destination_lat: float = Field(ge=-90, le=90)
    mode: str = "walking"
    safer_route_preference: bool = False


class TripResponse(BaseModel):
    id: UUID
    status: TripStatus
    mode: str
    safer_route_preference: bool
    started_at: datetime


class ShareTripRequest(BaseModel):
    contact_name: str = Field(min_length=1, max_length=255)
    channel: ShareChannel
    contact_address: str = Field(min_length=1, max_length=255)
    hours: int = Field(default=2, ge=1, le=24)


class TripShareResponse(BaseModel):
    id: UUID
    share_token: str
    expires_at: datetime


class CheckInRequest(BaseModel):
    expected_arrival_at: datetime
    contact_ref: str = Field(min_length=1, max_length=255)


class CheckInResponse(BaseModel):
    id: UUID
    expected_arrival_at: datetime
    confirmed_at: datetime | None
    alert_sent: bool


class CompanionModeRequest(BaseModel):
    origin_lon: float
    origin_lat: float
    destination_lon: float
    destination_lat: float
    mode: str = "walking"
    contact_name: str
    channel: ShareChannel
    contact_address: str
    expected_arrival_at: datetime


class CompanionModeResponse(BaseModel):
    trip: TripResponse
    share: TripShareResponse
    checkin: CheckInResponse


class SafePointResponse(BaseModel):
    name: str
    category: str
    lon: float
    lat: float


class QuickHelpResponse(BaseModel):
    numbers: dict[str, str]
    nearest_safe_points: list[SafePointResponse]
