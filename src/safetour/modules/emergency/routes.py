"""Emergency API routes (FR-EMG-1..4)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from safetour.modules.auth.dependencies import CurrentAccountId
from safetour.modules.emergency.dependencies import get_emergency_service
from safetour.modules.emergency.schemas import (
    CheckInRequest,
    CheckInResponse,
    CompanionModeRequest,
    CompanionModeResponse,
    QuickHelpResponse,
    SafePointResponse,
    ShareTripRequest,
    StartTripRequest,
    TripResponse,
    TripShareResponse,
)
from safetour.modules.emergency.service import CompanionModeInput, EmergencyService

router = APIRouter(tags=["emergency"])

EmergencyServiceDep = Annotated[EmergencyService, Depends(get_emergency_service)]


@router.get("/emergency/quick-help", response_model=QuickHelpResponse)
async def quick_help(
    service: EmergencyServiceDep,
    lon: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
) -> QuickHelpResponse:
    result = await service.quick_help(lon, lat)
    return QuickHelpResponse(
        numbers=result.numbers,
        nearest_safe_points=[SafePointResponse(**p) for p in result.nearest_safe_points],
    )


@router.post("/trips", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
async def start_trip(
    account_id: CurrentAccountId, body: StartTripRequest, service: EmergencyServiceDep
) -> TripResponse:
    trip = await service.start_trip(
        account_id, body.origin_lon, body.origin_lat, body.destination_lon, body.destination_lat,
        body.mode, body.safer_route_preference,
    )
    return TripResponse.model_validate(trip, from_attributes=True)


@router.post("/trips/{trip_id}/share", response_model=TripShareResponse)
async def share_trip(
    trip_id: UUID, account_id: CurrentAccountId, body: ShareTripRequest, service: EmergencyServiceDep
) -> TripShareResponse:
    share = await service.share_trip(
        trip_id, account_id, body.contact_name, body.channel, body.contact_address, body.hours
    )
    return TripShareResponse.model_validate(share, from_attributes=True)


@router.post("/trips/{trip_id}/checkin", response_model=CheckInResponse)
async def set_checkin(
    trip_id: UUID, account_id: CurrentAccountId, body: CheckInRequest, service: EmergencyServiceDep
) -> CheckInResponse:
    checkin = await service.set_checkin(trip_id, account_id, body.expected_arrival_at, body.contact_ref)
    return CheckInResponse.model_validate(checkin, from_attributes=True)


@router.post("/checkins/{checkin_id}/confirm", response_model=CheckInResponse)
async def confirm_checkin(checkin_id: UUID, service: EmergencyServiceDep) -> CheckInResponse:
    checkin = await service.confirm_arrival(checkin_id)
    return CheckInResponse.model_validate(checkin, from_attributes=True)


@router.get("/checkins/{checkin_id}/status", response_model=CheckInResponse)
async def checkin_status(checkin_id: UUID, service: EmergencyServiceDep) -> CheckInResponse:
    checkin = await service.check_overdue_and_alert(checkin_id)
    return CheckInResponse.model_validate(checkin, from_attributes=True)


@router.post("/trips/companion", response_model=CompanionModeResponse, status_code=status.HTTP_201_CREATED)
async def companion_mode(
    account_id: CurrentAccountId, body: CompanionModeRequest, service: EmergencyServiceDep
) -> CompanionModeResponse:
    trip, share, checkin = await service.companion_mode(
        CompanionModeInput(
            user_id=account_id, origin_lon=body.origin_lon, origin_lat=body.origin_lat,
            destination_lon=body.destination_lon, destination_lat=body.destination_lat, mode=body.mode,
            contact_name=body.contact_name, channel=body.channel, contact_address=body.contact_address,
            expected_arrival_at=body.expected_arrival_at,
        )
    )
    return CompanionModeResponse(
        trip=TripResponse.model_validate(trip, from_attributes=True),
        share=TripShareResponse.model_validate(share, from_attributes=True),
        checkin=CheckInResponse.model_validate(checkin, from_attributes=True),
    )
