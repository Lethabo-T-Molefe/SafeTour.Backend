"""Assistant API route: POST /assistant/plan (FR-ITIN-5)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from safetour.modules.assistant.dependencies import get_assistant_service
from safetour.modules.assistant.schemas import AssistantPlanRequest, AssistantPlanResponse
from safetour.modules.assistant.service import AssistantService
from safetour.modules.auth.dependencies import CurrentAccountId
from safetour.modules.itineraries.schemas import ItineraryResponse
from safetour.modules.risk.domain import TimeBand

router = APIRouter(prefix="/assistant", tags=["assistant"])

AssistantServiceDep = Annotated[AssistantService, Depends(get_assistant_service)]


@router.post("/plan", response_model=AssistantPlanResponse)
async def assistant_plan(
    account_id: CurrentAccountId, body: AssistantPlanRequest, service: AssistantServiceDep
) -> AssistantPlanResponse:
    time_band = body.time_band or TimeBand.from_time(datetime.now(UTC).time())
    result = await service.plan(account_id, body.message, time_band, body.precinct_id)
    return AssistantPlanResponse(
        reply_text=result.reply_text,
        itinerary=ItineraryResponse.model_validate(result.itinerary, from_attributes=True),
        used_llm=result.used_llm,
    )
