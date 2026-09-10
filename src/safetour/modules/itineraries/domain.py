"""Itineraries domain (FR-ITIN-1..3): generation folds in the "ranking"
component from 24.2 — a content-based fit score, safety re-ranked."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4


class ItineraryStatus(StrEnum):
    DRAFT = "draft"
    SAVED = "saved"
    COMPLETED = "completed"


@dataclass(slots=True)
class ItineraryStop:
    attraction_id: UUID
    order_index: int
    risk_band: str
    data_date: str | None
    rationale: str


@dataclass(slots=True)
class Itinerary:
    user_id: UUID
    status: ItineraryStatus = ItineraryStatus.DRAFT
    precinct_id: UUID | None = None
    stops: list[ItineraryStop] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ItineraryRepository(Protocol):
    async def add(self, itinerary: Itinerary) -> Itinerary: ...
    async def get(self, itinerary_id: UUID) -> Itinerary | None: ...
    async def list_for_user(self, user_id: UUID) -> list[Itinerary]: ...
    async def update(self, itinerary: Itinerary) -> Itinerary: ...


class ItineraryNotFoundError(Exception):
    def __init__(self) -> None:
        super().__init__("Itinerary not found")


class ItineraryForbiddenError(Exception):
    def __init__(self) -> None:
        super().__init__("This itinerary does not belong to the current user")
