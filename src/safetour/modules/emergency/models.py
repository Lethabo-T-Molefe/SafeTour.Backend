"""SQLAlchemy models and repositories for the emergency module."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CursorResult, DateTime, Float, ForeignKey, String, delete, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from safetour.modules.emergency.domain import CheckIn, ShareChannel, Trip, TripShare, TripStatus
from safetour.shared.database import Base


class TripModel(Base):
    __tablename__ = "trips"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("auth_accounts.id"), index=True, nullable=False
    )
    origin_lon: Mapped[float] = mapped_column(Float, nullable=False)
    origin_lat: Mapped[float] = mapped_column(Float, nullable=False)
    destination_lon: Mapped[float] = mapped_column(Float, nullable=False)
    destination_lat: Mapped[float] = mapped_column(Float, nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    safer_route_preference: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=TripStatus.ACTIVE.value, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TripShareModel(Base):
    __tablename__ = "trip_shares"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    trip_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), index=True, nullable=False
    )
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    contact_address: Mapped[str] = mapped_column(String(255), nullable=False)
    share_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CheckInModel(Base):
    __tablename__ = "checkins"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    trip_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), index=True, nullable=False
    )
    expected_arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    contact_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


def _trip_entity(row: TripModel) -> Trip:
    return Trip(
        id=row.id, user_id=row.user_id, origin_lon=row.origin_lon, origin_lat=row.origin_lat,
        destination_lon=row.destination_lon, destination_lat=row.destination_lat, mode=row.mode,
        safer_route_preference=row.safer_route_preference, status=TripStatus(row.status),
        started_at=row.started_at, ended_at=row.ended_at,
    )


class SqlAlchemyTripRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, trip: Trip) -> Trip:
        row = TripModel(
            id=trip.id, user_id=trip.user_id, origin_lon=trip.origin_lon, origin_lat=trip.origin_lat,
            destination_lon=trip.destination_lon, destination_lat=trip.destination_lat, mode=trip.mode,
            safer_route_preference=trip.safer_route_preference, status=trip.status.value,
        )
        self._session.add(row)
        await self._session.flush()
        return _trip_entity(row)

    async def get(self, trip_id: UUID) -> Trip | None:
        row = await self._session.get(TripModel, trip_id)
        return _trip_entity(row) if row else None

    async def update(self, trip: Trip) -> Trip:
        row = await self._session.get(TripModel, trip.id)
        if row is not None:
            row.status = trip.status.value
            row.ended_at = trip.ended_at
            await self._session.flush()
        return trip


class SqlAlchemyTripShareRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, share: TripShare) -> TripShare:
        row = TripShareModel(
            id=share.id, trip_id=share.trip_id, contact_name=share.contact_name, channel=share.channel.value,
            contact_address=share.contact_address, share_token=share.share_token, expires_at=share.expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        return share

    async def get(self, share_id: UUID) -> TripShare | None:
        row = await self._session.get(TripShareModel, share_id)
        if row is None:
            return None
        return TripShare(
            id=row.id, trip_id=row.trip_id, contact_name=row.contact_name, channel=ShareChannel(row.channel),
            contact_address=row.contact_address, share_token=row.share_token, expires_at=row.expires_at,
            revoked_at=row.revoked_at, created_at=row.created_at,
        )

    async def purge_expired(self, *, before: datetime) -> int:
        result = await self._session.execute(delete(TripShareModel).where(TripShareModel.expires_at < before))
        await self._session.flush()
        return cast(CursorResult[Any], result).rowcount or 0


class SqlAlchemyCheckInRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, checkin: CheckIn) -> CheckIn:
        row = CheckInModel(
            id=checkin.id, trip_id=checkin.trip_id, expected_arrival_at=checkin.expected_arrival_at,
            contact_ref=checkin.contact_ref,
        )
        self._session.add(row)
        await self._session.flush()
        return checkin

    async def get(self, checkin_id: UUID) -> CheckIn | None:
        row = await self._session.get(CheckInModel, checkin_id)
        if row is None:
            return None
        return CheckIn(
            id=row.id, trip_id=row.trip_id, expected_arrival_at=row.expected_arrival_at,
            contact_ref=row.contact_ref, confirmed_at=row.confirmed_at, alert_sent=row.alert_sent,
        )

    async def update(self, checkin: CheckIn) -> CheckIn:
        row = await self._session.get(CheckInModel, checkin.id)
        if row is not None:
            row.confirmed_at = checkin.confirmed_at
            row.alert_sent = checkin.alert_sent
            await self._session.flush()
        return checkin

    async def purge_expired(self, *, before: datetime) -> int:
        result = await self._session.execute(delete(CheckInModel).where(CheckInModel.expected_arrival_at < before))
        await self._session.flush()
        return cast(CursorResult[Any], result).rowcount or 0
