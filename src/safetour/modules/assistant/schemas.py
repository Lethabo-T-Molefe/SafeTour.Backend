from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from safetour.modules.itineraries.schemas import ItineraryResponse
from safetour.modules.risk.domain import TimeBand


class AssistantPlanRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    precinct_id: UUID | None = None
    time_band: TimeBand | None = None


class AssistantPlanResponse(BaseModel):
    reply_text: str
    itinerary: ItineraryResponse
    used_llm: bool = Field(
        description="True if the contained LLM interpreted the request; false if the deterministic matcher did"
    )
