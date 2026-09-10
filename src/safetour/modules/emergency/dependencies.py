from typing import Annotated

from fastapi import Depends

from safetour.modules.emergency.models import (
    SqlAlchemyCheckInRepository,
    SqlAlchemyTripRepository,
    SqlAlchemyTripShareRepository,
)
from safetour.modules.emergency.service import EmergencyService
from safetour.modules.geo.dependencies import get_geo_repository
from safetour.modules.geo.models import SqlAlchemyGeoReadRepository
from safetour.modules.notifications.dependencies import get_notifications_port
from safetour.modules.notifications.service import NotificationsService
from safetour.shared.dependencies import DbSession


def get_emergency_service(
    db: DbSession,
    geo: Annotated[SqlAlchemyGeoReadRepository, Depends(get_geo_repository)],
    notifications: Annotated[NotificationsService, Depends(get_notifications_port)],
) -> EmergencyService:
    return EmergencyService(
        trips=SqlAlchemyTripRepository(db),
        shares=SqlAlchemyTripShareRepository(db),
        checkins=SqlAlchemyCheckInRepository(db),
        geo=geo,
        notifications=notifications,
    )
