"""SQLAlchemy model and repository for itineraries.

Stops are a small (<=5), always-together list, so they are stored as a JSONB
array on the itinerary row rather than a join table — simpler reads/writes
with no loss of query capability we actually need.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from safetour.modules.itineraries.domain import (
    Itinerary,
    ItineraryStatus,
    ItineraryStop,
)
from safetour.shared.database import Base


class ItineraryModel(Base):
    __tablename__ = "itineraries"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("auth_accounts.id"), index=True, nullable=False
    )
    precinct_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=ItineraryStatus.DRAFT.value, nullable=False)
    stops: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def _stop_to_dict(stop: ItineraryStop) -> dict[str, Any]:
    return {
        "attraction_id": str(stop.attraction_id),
        "order_index": stop.order_index,
        "risk_band": stop.risk_band,
        "data_date": stop.data_date,
        "rationale": stop.rationale,
    }


def _stop_from_dict(data: dict[str, Any]) -> ItineraryStop:
    return ItineraryStop(
        attraction_id=UUID(data["attraction_id"]),
        order_index=data["order_index"],
        risk_band=data["risk_band"],
        data_date=data.get("data_date"),
        rationale=data["rationale"],
    )


def _to_entity(row: ItineraryModel) -> Itinerary:
    return Itinerary(
        id=row.id,
        user_id=row.user_id,
        precinct_id=row.precinct_id,
        status=ItineraryStatus(row.status),
        stops=[_stop_from_dict(s) for s in row.stops],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyItineraryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, itinerary: Itinerary) -> Itinerary:
        row = ItineraryModel(
            id=itinerary.id, user_id=itinerary.user_id, precinct_id=itinerary.precinct_id,
            status=itinerary.status.value, stops=[_stop_to_dict(s) for s in itinerary.stops],
        )
        self._session.add(row)
        await self._session.flush()
        return _to_entity(row)

    async def get(self, itinerary_id: UUID) -> Itinerary | None:
        row = await self._session.get(ItineraryModel, itinerary_id)
        return _to_entity(row) if row else None

    async def list_for_user(self, user_id: UUID) -> list[Itinerary]:
        result = await self._session.execute(
            select(ItineraryModel).where(ItineraryModel.user_id == user_id).order_by(ItineraryModel.created_at.desc())
        )
        return [_to_entity(r) for r in result.scalars().all()]

    async def update(self, itinerary: Itinerary) -> Itinerary:
        row = await self._session.get(ItineraryModel, itinerary.id)
        if row is not None:
            row.status = itinerary.status.value
            row.stops = [_stop_to_dict(s) for s in itinerary.stops]
            await self._session.flush()
        return itinerary
