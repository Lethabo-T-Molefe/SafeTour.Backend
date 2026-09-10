"""
Notifications application service.

``send_alert`` also implements ``emergency.domain.NotificationsPort`` by
structural typing — it always writes an ``AlertLogEntry`` (the "in-app
indicator" fallback from the integrations table), which is the only channel
guaranteed to work with no push/SMS gateway configured.
"""

from __future__ import annotations

from uuid import UUID

from safetour.modules.notifications.domain import (
    AlertLogEntry,
    AlertLogRepository,
    AlertPreference,
    AlertPreferenceRepository,
    PushSubscription,
    PushSubscriptionRepository,
)


class NotificationsService:
    def __init__(
        self,
        subscriptions: PushSubscriptionRepository,
        preferences: AlertPreferenceRepository,
        alert_log: AlertLogRepository,
    ) -> None:
        self._subscriptions = subscriptions
        self._preferences = preferences
        self._alert_log = alert_log

    async def subscribe(self, user_id: UUID, endpoint: str, keys: dict[str, str]) -> PushSubscription:
        return await self._subscriptions.add(PushSubscription(user_id=user_id, endpoint=endpoint, keys=keys))

    async def get_preferences(self, user_id: UUID) -> AlertPreference:
        preference = await self._preferences.get(user_id)
        return preference or AlertPreference(user_id=user_id)

    async def update_preferences(self, user_id: UUID, non_safety_opt_in: bool) -> AlertPreference:
        preference = await self.get_preferences(user_id)
        preference.non_safety_opt_in = non_safety_opt_in
        return await self._preferences.upsert(preference)

    async def send_alert(self, *, recipient: str, channel: object, message: str) -> None:
        channel_value = getattr(channel, "value", str(channel))
        await self._alert_log.add(AlertLogEntry(recipient=recipient, channel=channel_value, message=message))
