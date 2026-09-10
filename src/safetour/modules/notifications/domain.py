"""Notifications domain (FR-NOT-2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4


@dataclass(slots=True)
class PushSubscription:
    user_id: UUID
    endpoint: str
    keys: dict[str, str]
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class AlertPreference:
    user_id: UUID
    safety_alerts_opt_in: bool = True  # not user-configurable — safety alerts cannot be opted out of
    non_safety_opt_in: bool = False


@dataclass(slots=True)
class AlertLogEntry:
    recipient: str
    channel: str
    message: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class PushSubscriptionRepository(Protocol):
    async def add(self, subscription: PushSubscription) -> PushSubscription: ...
    async def list_for_user(self, user_id: UUID) -> list[PushSubscription]: ...


class AlertPreferenceRepository(Protocol):
    async def get(self, user_id: UUID) -> AlertPreference | None: ...
    async def upsert(self, preference: AlertPreference) -> AlertPreference: ...


class AlertLogRepository(Protocol):
    async def add(self, entry: AlertLogEntry) -> AlertLogEntry: ...
    async def list_recent(self, *, limit: int = 50) -> list[AlertLogEntry]: ...
