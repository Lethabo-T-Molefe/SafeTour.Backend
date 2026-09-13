"""
Conversational assistant (FR-ITIN-5, MLR-6).

Architecture decision (24.4): "Language model contained — a read-only
orchestrator with a provenance validator, never the source of a risk value."
Concretely: the assistant only ever extracts *intent* (which interests the
free text mentions) from either an LLM call or a deterministic keyword
matcher — every place, risk band and rationale in the reply still comes
from ``ItineraryService.generate``, i.e. from the database, never invented
by the model. The LLM path cannot smuggle a fabricated place name or risk
claim into the response because its only output (a handful of keywords)
feeds the same content-based ranker the deterministic path uses; there is
no code path where LLM text reaches the user directly.

With no ``LLM_API_KEY`` configured (the zero-cost default), the
deterministic matcher is the only path exercised, so the feature works with
no external dependency and no per-request cost. Any LLM failure — missing
key, network error, malformed output — falls back to the deterministic
matcher rather than failing the request (NFR-REL-2).
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

_MAX_KEYWORDS = 5
_MAX_KEYWORD_LENGTH = 30
_ORCHESTRATOR_SYSTEM_PROMPT = (
    "You extract search interests from a traveller's message for a safety-aware "
    "itinerary planner. Reply with ONLY a comma-separated list of 1 to 5 short "
    "lowercase English keywords describing what they want to see or do (for "
    "example: market, museum, nightlife, food, park). "
    "Never output a place name, address, risk level, safety claim, or any text "
    "other than the keyword list — those are resolved separately from a "
    "database, not from you."
)


@dataclass(slots=True)
class AssistantPlanOutput:
    reply_text: str
    itinerary: Itinerary
    used_llm: bool


def _extract_interests(free_text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z]+", free_text.lower())
    interests = {word for word in words if word in _KEYWORD_TO_CATEGORY}
    return sorted(interests) or [w for w in words if len(w) > 3][:3]


def _validate_llm_keywords(raw: str) -> list[str] | None:
    """Provenance validator: the LLM may only hand back short, plain keyword
    tokens. Anything else (sentences, punctuation-heavy text, suspiciously
    long output) is rejected rather than trusted, since the failure mode of
    a prompt-injected or hallucinating model here is fabricated content
    slipping downstream — reject and fall back instead of guessing."""
    candidates = [part.strip().lower() for part in raw.split(",")]
    keywords = [
        word
        for word in candidates
        if word and len(word) <= _MAX_KEYWORD_LENGTH and re.fullmatch(r"[a-z][a-z \-]*", word)
    ]
    return keywords[:_MAX_KEYWORDS] or None


async def _try_llm_intent(free_text: str) -> list[str] | None:
    """Read-only orchestrator call: the LLM's only allowed output is a short
    keyword list (see ``_ORCHESTRATOR_SYSTEM_PROMPT``), validated by
    ``_validate_llm_keywords`` before use. Returns ``None`` — triggering the
    deterministic fallback — whenever no key is configured or anything about
    the call goes wrong."""
    if not settings.LLM_API_KEY:
        return None
    try:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage, SystemMessage

        # langchain-anthropic's pydantic field aliasing confuses mypy's view of this
        # constructor's kwargs even though `model=`/`api_key=` are the documented,
        # runtime-verified names.
        model = ChatAnthropic(  # type: ignore[call-arg]
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,  # type: ignore[arg-type]
            max_tokens=64,
            temperature=0,
            timeout=8.0,
        )
        response = await model.ainvoke(
            [SystemMessage(content=_ORCHESTRATOR_SYSTEM_PROMPT), HumanMessage(content=free_text[:500])]
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        return _validate_llm_keywords(content)
    except Exception:
        return None


class AssistantService:
    def __init__(self, itineraries: ItineraryService) -> None:
        self._itineraries = itineraries

    async def plan(
        self, user_id: UUID, free_text: str, time_band: TimeBand, precinct_id: UUID | None = None
    ) -> AssistantPlanOutput:
        llm_interests = await _try_llm_intent(free_text)
        interests = llm_interests or _extract_interests(free_text)
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
        return AssistantPlanOutput(reply_text=reply, itinerary=itinerary, used_llm=llm_interests is not None)
