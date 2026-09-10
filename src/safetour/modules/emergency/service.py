"""Emergency application service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from safetour.modules.emergency.domain import (
    CheckIn,
    CheckInRepository,
    NotificationsPort,
    ShareChannel,
    ShareWindowTooLongError,
    Trip,
    TripForbiddenError,
    TripNotFoundError,
    TripRepository,
    TripShare,
    TripShareRepository,
    default_share_expiry,
)
from safetour.modules.geo.domain import AttractionCategory, GeoReadRepository
from safetour.shared.config import settings

_QUICK_HELP_NUMBERS = {
    "SAPS (police)": "10111",
    "Ambulance": "10177",
    "GBV Command Centre": "0800 428 428",
    "Cell emergency (any network)": "112",
}
_SAFE_POINT_RADIUS_M = 3000.0


@dataclass(slots=True)
class CompanionModeInput:
    user_id: UUID
    origin_lon: float
    origin_lat: float
    destination_lon: float
    destination_lat: float
    mode: str
    contact_name: str
    channel: ShareChannel
    contact_address: str
    expected_arrival_at: datetime


@dataclass(slots=True)
class QuickHelpOutput:
    numbers: dict[str, str]
    nearest_safe_points: list[dict[str, Any]]


class EmergencyService:
    def __init__(
        self,
        trips: TripRepository,
        shares: TripShareRepository,
        checkins: CheckInRepository,
        geo: GeoReadRepository,
        notifications: NotificationsPort | None = None,
    ) -> None:
        self._trips = trips
        self._shares = shares
        self._checkins = checkins
        self._geo = geo
        self._notifications = notifications

    async def start_trip(
        self, user_id: UUID, origin_lon: float, origin_lat: float, destination_lon: float,
        destination_lat: float, mode: str, safer_route_preference: bool = False,
    ) -> Trip:
        trip = Trip(
            user_id=user_id, origin_lon=origin_lon, origin_lat=origin_lat,
            destination_lon=destination_lon, destination_lat=destination_lat, mode=mode,
            safer_route_preference=safer_route_preference,
        )
        return await self._trips.add(trip)

    async def share_trip(
        self, trip_id: UUID, user_id: UUID, contact_name: str, channel: ShareChannel,
        contact_address: str, hours: int,
    ) -> TripShare:
        await self._require_owned_trip(trip_id, user_id)
        if hours > settings.TRIP_SHARE_MAX_HOURS:
            raise ShareWindowTooLongError(settings.TRIP_SHARE_MAX_HOURS)
        expires_at = min(default_share_expiry(hours), default_share_expiry(settings.TRIP_SHARE_MAX_HOURS))
        share = TripShare(
            trip_id=trip_id, contact_name=contact_name, channel=channel,
            contact_address=contact_address, expires_at=expires_at,
        )
        return await self._shares.add(share)

    async def set_checkin(
        self, trip_id: UUID, user_id: UUID, expected_arrival_at: datetime, contact_ref: str
    ) -> CheckIn:
        await self._require_owned_trip(trip_id, user_id)
        checkin = CheckIn(trip_id=trip_id, expected_arrival_at=expected_arrival_at, contact_ref=contact_ref)
        return await self._checkins.add(checkin)

    async def confirm_arrival(self, checkin_id: UUID) -> CheckIn:
        checkin = await self._checkins.get(checkin_id)
        if checkin is None:
            raise TripNotFoundError()
        checkin.confirm()
        return await self._checkins.update(checkin)

    async def check_overdue_and_alert(self, checkin_id: UUID) -> CheckIn:
        """Poll-on-read: a client (or the admin purge job) calls this to learn
        whether a check-in is overdue; the alert fires at most once per check-in."""
        checkin = await self._checkins.get(checkin_id)
        if checkin is None:
            raise TripNotFoundError()
        if checkin.is_overdue() and not checkin.alert_sent:
            if self._notifications is not None:
                await self._notifications.send_alert(
                    recipient=checkin.contact_ref,
                    channel=ShareChannel.SMS,
                    message="Your SafeTour contact has not confirmed arrival at the expected time.",
                )
            checkin.alert_sent = True
            checkin = await self._checkins.update(checkin)
        return checkin

    async def companion_mode(self, data: CompanionModeInput) -> tuple[Trip, TripShare, CheckIn]:
        """FR-EMG-4: live sharing + a check-in + a safer-route preference, in one call."""
        trip = await self.start_trip(
            data.user_id, data.origin_lon, data.origin_lat, data.destination_lon, data.destination_lat,
            data.mode, safer_route_preference=True,
        )
        hours = max(1, int((data.expected_arrival_at - datetime.now(UTC)).total_seconds() // 3600) + 1)
        share = await self.share_trip(
            trip.id, data.user_id, data.contact_name, data.channel, data.contact_address, hours
        )
        checkin = await self.set_checkin(trip.id, data.user_id, data.expected_arrival_at, data.contact_address)
        return trip, share, checkin

    async def quick_help(self, lon: float, lat: float) -> QuickHelpOutput:
        """FR-EMG-1: one interaction, numbers plus the nearest known safe points."""
        safe_points = await self._geo.list_attractions(
            category=AttractionCategory.SAFE_POINT, near=(lon, lat), radius_m=_SAFE_POINT_RADIUS_M, limit=5
        )
        police = await self._geo.list_attractions(
            category=AttractionCategory.POLICE_STATION, near=(lon, lat), radius_m=_SAFE_POINT_RADIUS_M, limit=3
        )
        nearest = [
            {"name": p.name, "category": p.category.value, "lon": p.location.x, "lat": p.location.y}
            for p in [*safe_points, *police]
        ]
        return QuickHelpOutput(numbers=dict(_QUICK_HELP_NUMBERS), nearest_safe_points=nearest)

    async def _require_owned_trip(self, trip_id: UUID, user_id: UUID) -> Trip:
        trip = await self._trips.get(trip_id)
        if trip is None:
            raise TripNotFoundError()
        if trip.user_id != user_id:
            raise TripForbiddenError()
        return trip
