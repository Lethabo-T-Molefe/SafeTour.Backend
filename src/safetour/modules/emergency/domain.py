"""
Emergency domain (FR-EMG-1..4).

NFR-PRIV-2/PRIV-4: trip shares and check-ins are opt-in, time-boxed and
transient by construction — every share and check-in carries an
``expires_at``/derives one from the trip, and a purge job (admin module)
hard-deletes rows past that point rather than relying on the application
layer to keep hiding them forever.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4


class TripStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ShareChannel(StrEnum):
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"


@dataclass(slots=True)
class Trip:
    user_id: UUID
    origin_lon: float
    origin_lat: float
    destination_lon: float
    destination_lat: float
    mode: str
    safer_route_preference: bool = False
    status: TripStatus = TripStatus.ACTIVE
    id: UUID = field(default_factory=uuid4)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None

    def end(self) -> None:
        self.status = TripStatus.COMPLETED
        self.ended_at = datetime.now(UTC)


@dataclass(slots=True)
class TripShare:
    trip_id: UUID
    contact_name: str
    channel: ShareChannel
    contact_address: str
    expires_at: datetime
    id: UUID = field(default_factory=uuid4)
    share_token: str = field(default_factory=lambda: uuid4().hex)
    revoked_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > datetime.now(UTC)


@dataclass(slots=True)
class CheckIn:
    trip_id: UUID
    expected_arrival_at: datetime
    contact_ref: str
    id: UUID = field(default_factory=uuid4)
    confirmed_at: datetime | None = None
    alert_sent: bool = False

    def is_overdue(self) -> bool:
        return self.confirmed_at is None and datetime.now(UTC) > self.expected_arrival_at

    def confirm(self) -> None:
        self.confirmed_at = datetime.now(UTC)


class TripRepository(Protocol):
    async def add(self, trip: Trip) -> Trip: ...
    async def get(self, trip_id: UUID) -> Trip | None: ...
    async def update(self, trip: Trip) -> Trip: ...


class TripShareRepository(Protocol):
    async def add(self, share: TripShare) -> TripShare: ...
    async def get(self, share_id: UUID) -> TripShare | None: ...
    async def purge_expired(self, *, before: datetime) -> int: ...


class CheckInRepository(Protocol):
    async def add(self, checkin: CheckIn) -> CheckIn: ...
    async def get(self, checkin_id: UUID) -> CheckIn | None: ...
    async def update(self, checkin: CheckIn) -> CheckIn: ...
    async def purge_expired(self, *, before: datetime) -> int: ...


class NotificationsPort(Protocol):
    """Loose coupling to the notifications module (FR-NOT-2)."""

    async def send_alert(self, *, recipient: str, channel: ShareChannel, message: str) -> None: ...


class TripNotFoundError(Exception):
    def __init__(self) -> None:
        super().__init__("Trip not found")


class TripForbiddenError(Exception):
    def __init__(self) -> None:
        super().__init__("This trip does not belong to the current user")


class ShareWindowTooLongError(Exception):
    def __init__(self, max_hours: int) -> None:
        super().__init__(f"A trip share cannot exceed {max_hours} hours (NFR-PRIV-4: time-boxed)")


def default_share_expiry(max_hours: int) -> datetime:
    return datetime.now(UTC) + timedelta(hours=max_hours)
