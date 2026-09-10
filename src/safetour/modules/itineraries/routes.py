"""Itineraries API routes (FR-ITIN-1..3)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from safetour.modules.auth.dependencies import CurrentAccountId
from safetour.modules.itineraries.dependencies import get_itinerary_service
from safetour.modules.itineraries.schemas import ItineraryGenerateRequest, ItineraryResponse
from safetour.modules.itineraries.service import GenerateItineraryInput, ItineraryService
from safetour.modules.risk.domain import TimeBand

router = APIRouter(prefix="/itineraries", tags=["itineraries"])

ItineraryServiceDep = Annotated[ItineraryService, Depends(get_itinerary_service)]


@router.post("", response_model=ItineraryResponse, status_code=status.HTTP_201_CREATED)
async def generate_itinerary(
    account_id: CurrentAccountId, body: ItineraryGenerateRequest, service: ItineraryServiceDep
) -> ItineraryResponse:
    time_band = body.time_band or TimeBand.from_time(datetime.now(UTC).time())
    itinerary = await service.generate(
        GenerateItineraryInput(
            user_id=account_id, time_band=time_band, precinct_id=body.precinct_id, interests=body.interests
        )
    )
    return ItineraryResponse.model_validate(itinerary, from_attributes=True)


@router.get("", response_model=list[ItineraryResponse])
async def list_my_itineraries(account_id: CurrentAccountId, service: ItineraryServiceDep) -> list[ItineraryResponse]:
    itineraries = await service.list_for_user(account_id)
    return [ItineraryResponse.model_validate(i, from_attributes=True) for i in itineraries]


@router.get("/{itinerary_id}", response_model=ItineraryResponse)
async def get_itinerary(
    itinerary_id: UUID,
    account_id: CurrentAccountId,
    service: ItineraryServiceDep,
    time_band: TimeBand | None = None,
) -> ItineraryResponse:
    resolved_band = time_band or TimeBand.from_time(datetime.now(UTC).time())
    itinerary = await service.get(itinerary_id, account_id, resolved_band)
    return ItineraryResponse.model_validate(itinerary, from_attributes=True)


@router.put("/{itinerary_id}/save", response_model=ItineraryResponse)
async def save_itinerary(
    itinerary_id: UUID, account_id: CurrentAccountId, service: ItineraryServiceDep
) -> ItineraryResponse:
    itinerary = await service.save(itinerary_id, account_id)
    return ItineraryResponse.model_validate(itinerary, from_attributes=True)
