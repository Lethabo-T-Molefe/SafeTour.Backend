from safetour.modules.notifications.models import (
    SqlAlchemyAlertLogRepository,
    SqlAlchemyAlertPreferenceRepository,
    SqlAlchemyPushSubscriptionRepository,
)
from safetour.modules.notifications.service import NotificationsService
from safetour.shared.dependencies import DbSession


def get_notifications_port(db: DbSession) -> NotificationsService:
    return NotificationsService(
        subscriptions=SqlAlchemyPushSubscriptionRepository(db),
        preferences=SqlAlchemyAlertPreferenceRepository(db),
        alert_log=SqlAlchemyAlertLogRepository(db),
    )
