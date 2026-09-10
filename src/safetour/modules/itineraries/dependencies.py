from typing import Annotated

from fastapi import Depends

from safetour.modules.geo.dependencies import get_geo_repository
from safetour.modules.geo.models import SqlAlchemyGeoReadRepository
from safetour.modules.itineraries.models import SqlAlchemyItineraryRepository
from safetour.modules.itineraries.service import ItineraryService
from safetour.modules.risk.dependencies import get_risk_service
from safetour.modules.risk.service import RiskService
from safetour.shared.dependencies import DbSession


def get_itinerary_service(
    db: DbSession,
    geo: Annotated[SqlAlchemyGeoReadRepository, Depends(get_geo_repository)],
    risk: Annotated[RiskService, Depends(get_risk_service)],
) -> ItineraryService:
    return ItineraryService(geo=geo, risk=risk, itineraries=SqlAlchemyItineraryRepository(db))
