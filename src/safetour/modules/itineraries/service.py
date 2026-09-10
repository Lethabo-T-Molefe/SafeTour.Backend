"""
Itinerary application service.

``generate`` is the naive placeholder for the real content-based recommender
+ safety re-rank (deliverable: "Recommendation engine", scikit-learn):
preference fit is a simple keyword match against attraction names/categories,
blended with inverted risk. The persisted shape (``Itinerary``/``ItineraryStop``)
does not need to change once the real ranker lands — only ``_score_candidate``
does.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from safetour.modules.geo.domain import AttractionStop, GeoReadRepository
from safetour.modules.itineraries.domain import (
    Itinerary,
    ItineraryForbiddenError,
    ItineraryNotFoundError,
    ItineraryRepository,
    ItineraryStatus,
    ItineraryStop,
)
from safetour.modules.risk.domain import TimeBand
from safetour.modules.risk.service import RiskService

_MAX_STOPS = 5
_CANDIDATE_POOL = 30


def _matching_interest(attraction: AttractionStop, interests: list[str]) -> str | None:
    haystack = f"{attraction.name.lower()} {attraction.category.value}"
    return next((interest for interest in interests if interest in haystack), None)


@dataclass(slots=True)
class GenerateItineraryInput:
    user_id: UUID
    time_band: TimeBand
    precinct_id: UUID | None = None
    interests: list[str] | None = None
    max_stops: int = _MAX_STOPS


class ItineraryService:
    def __init__(self, geo: GeoReadRepository, risk: RiskService, itineraries: ItineraryRepository) -> None:
        self._geo = geo
        self._risk = risk
        self._itineraries = itineraries

    async def generate(self, data: GenerateItineraryInput) -> Itinerary:
        candidates = await self._geo.list_attractions(precinct_id=data.precinct_id, limit=_CANDIDATE_POOL)
        interests = [i.lower() for i in (data.interests or [])]

        scored: list[tuple[float, AttractionStop, ItineraryStop]] = []
        for attraction in candidates:
            risk = await self._risk.lookup(attraction.location.x, attraction.location.y, data.time_band)
            risk_score = risk.score if risk.score is not None else 0.5  # neutral when unscored
            matched = _matching_interest(attraction, interests)
            preference_fit = 1.0 if matched else 0.5
            combined = 0.6 * preference_fit + 0.4 * (1 - risk_score)

            rationale = (
                f"{risk.band.value.replace('_', ' ')} risk"
                + (f", data as of {risk.data_date}" if risk.data_date else ", risk data not yet available")
                + (f"; matches your interest in {matched}" if matched else "")
            )
            stop = ItineraryStop(
                attraction_id=attraction.id, order_index=0, risk_band=risk.band.value,
                data_date=risk.data_date, rationale=rationale,
            )
            scored.append((combined, attraction, stop))

        scored.sort(key=lambda t: t[0], reverse=True)
        chosen = scored[: data.max_stops]
        for index, (_score, _attraction, stop) in enumerate(chosen):
            stop.order_index = index

        itinerary = Itinerary(
            user_id=data.user_id,
            precinct_id=data.precinct_id,
            stops=[stop for _s, _a, stop in chosen],
        )
        return await self._itineraries.add(itinerary)

    async def get(self, itinerary_id: UUID, user_id: UUID, time_band: TimeBand) -> Itinerary:
        itinerary = await self._require_owned(itinerary_id, user_id)
        # FR-ITIN-3: re-evaluate risk against the current model on every read.
        for stop in itinerary.stops:
            attraction = await self._geo.get_attraction(stop.attraction_id)
            if attraction is None:
                continue
            risk = await self._risk.lookup(attraction.location.x, attraction.location.y, time_band)
            stop.risk_band = risk.band.value
            stop.data_date = risk.data_date
        return itinerary

    async def list_for_user(self, user_id: UUID) -> list[Itinerary]:
        return await self._itineraries.list_for_user(user_id)

    async def save(self, itinerary_id: UUID, user_id: UUID) -> Itinerary:
        itinerary = await self._require_owned(itinerary_id, user_id)
        itinerary.status = ItineraryStatus.SAVED
        return await self._itineraries.update(itinerary)

    async def _require_owned(self, itinerary_id: UUID, user_id: UUID) -> Itinerary:
        itinerary = await self._itineraries.get(itinerary_id)
        if itinerary is None:
            raise ItineraryNotFoundError()
        if itinerary.user_id != user_id:
            raise ItineraryForbiddenError()
        return itinerary
