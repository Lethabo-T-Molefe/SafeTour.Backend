"""
Conversational assistant (FR-ITIN-5, MLR-6).

Architecture decision (24.4): "Language model contained — a read-only
orchestrator with a provenance validator, never the source of a risk value."
Concretely: the assistant only ever extracts *intent* (which interests the
free text mentions) from either an LLM call or a deterministic keyword
matcher: every place, risk band and rationale in the reply still comes from
``ItineraryService.generate`` — i.e. from the database — never invented by
the model. With no ``LLM_API_KEY`` configured (the zero-cost default), the
deterministic matcher is the only path exercised, so the feature works with
no external dependency and no per-request cost.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from safetour.modules.geo.domain import AttractionCategory
from safetour.modules.itineraries.domain import Itinerary
from safetour.modules.itineraries.service import GenerateItineraryInput, ItineraryService
from safetour.modules.risk.domain import TimeBand
from safetour.shared.config import settings

_KEYWORD_TO_CATEGORY = {
    "market": AttractionCategory.MARKET,
    "shopping": AttractionCategory.MARKET,
    "taxi": AttractionCategory.TAXI_RANK,
    "rank": AttractionCategory.TAXI_RANK,
    "bus": AttractionCategory.BUS_STOP,
    "train": AttractionCategory.RAIL_STATION,
    "rail": AttractionCategory.RAIL_STATION,
}


@dataclass(slots=True)
class AssistantPlanOutput:
    reply_text: str
    itinerary: Itinerary


def _extract_interests(free_text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z]+", free_text.lower())
    interests = {word for word in words if word in _KEYWORD_TO_CATEGORY}
    return sorted(interests) or [w for w in words if len(w) > 3][:3]


async def _try_llm_intent(free_text: str) -> list[str] | None:
    """Extension point for a real LangChain-orchestrated call. Returns only an
    intent (interest keywords) — never a place name or risk figure — so that
    everything shown to the user is still resolved from the database by
    ``ItineraryService``. Inert (returns ``None``) with no LLM key configured,
    which is the default for the zero-cost prototype."""
    if not settings.LLM_API_KEY:
        return None
    return None  # pragma: no cover - no provider wired up in the free-tier prototype


class AssistantService:
    def __init__(self, itineraries: ItineraryService) -> None:
        self._itineraries = itineraries

    async def plan(
        self, user_id: UUID, free_text: str, time_band: TimeBand, precinct_id: UUID | None = None
    ) -> AssistantPlanOutput:
        interests = await _try_llm_intent(free_text) or _extract_interests(free_text)
        itinerary = await self._itineraries.generate(
            GenerateItineraryInput(
                user_id=user_id, time_band=time_band, precinct_id=precinct_id, interests=interests
            )
        )
        if itinerary.stops:
            reply = (
                f"Based on \"{free_text.strip()}\", here is a {len(itinerary.stops)}-stop plan, "
                "ranked for fit and safety. Every stop shows its current risk band and data date — "
                "nothing here is a guarantee of safety."
            )
        else:
            reply = (
                "I couldn't find enough scored places nearby for that request yet — "
                "try a different area or check back once more data has been ingested."
            )
        return AssistantPlanOutput(reply_text=reply, itinerary=itinerary)
