"""
Itinerary application service.

``generate`` calls the content-based ranker + safety re-rank in
``recommender.py`` (deliverable: "Recommendation engine", scikit-learn) —
the service's only job here is gathering each candidate's text and current
risk score and turning the ranked result back into persisted stops.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from safetour.modules.geo.domain import GeoReadRepository
from safetour.modules.itineraries.domain import (
    Itinerary,
    ItineraryForbiddenError,
    ItineraryNotFoundError,
    ItineraryRepository,
    ItineraryStatus,
    ItineraryStop,
)
from safetour.modules.itineraries.recommender import RankingCandidate, content_based_rank
from safetour.modules.risk.domain import TimeBand
from safetour.modules.risk.service import RiskService

_MAX_STOPS = 5
_CANDIDATE_POOL = 30


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
        attractions = await self._geo.list_attractions(precinct_id=data.precinct_id, limit=_CANDIDATE_POOL)
        if not attractions:
            return await self._itineraries.add(Itinerary(user_id=data.user_id, precinct_id=data.precinct_id, stops=[]))

        by_id = {a.id: a for a in attractions}
        risk_by_id = {}
        candidates = []
        for attraction in attractions:
            risk = await self._risk.lookup(attraction.location.x, attraction.location.y, data.time_band)
            risk_by_id[attraction.id] = risk
            candidates.append(
                RankingCandidate(
                    attraction_id=attraction.id,
                    document=f"{attraction.name} {attraction.category.value}",
                    risk_score=risk.score if risk.score is not None else 0.5,  # neutral when unscored
                )
            )

        ranked = content_based_rank(candidates, [i.lower() for i in (data.interests or [])])

        stops: list[ItineraryStop] = []
        for order_index, result in enumerate(ranked[: data.max_stops]):
            attraction = by_id[result.attraction_id]
            risk = risk_by_id[result.attraction_id]
            rationale = (
                f"{risk.band.value.replace('_', ' ')} risk"
                + (f", data as of {risk.data_date}" if risk.data_date else ", risk data not yet available")
                + (f"; matches your interest in {result.matched_terms[0]}" if result.matched_terms else "")
            )
            stops.append(
                ItineraryStop(
                    attraction_id=attraction.id, order_index=order_index, risk_band=risk.band.value,
                    data_date=risk.data_date, rationale=rationale,
                )
            )

        itinerary = Itinerary(user_id=data.user_id, precinct_id=data.precinct_id, stops=stops)
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
