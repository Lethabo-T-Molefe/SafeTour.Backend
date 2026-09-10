from typing import Annotated

from fastapi import Depends

from safetour.modules.geo.dependencies import get_geo_repository
from safetour.modules.geo.models import SqlAlchemyGeoReadRepository
from safetour.modules.risk.dependencies import get_risk_service
from safetour.modules.risk.service import RiskService
from safetour.modules.routing.service import RoutingService


def get_routing_service(
    geo: Annotated[SqlAlchemyGeoReadRepository, Depends(get_geo_repository)],
    risk: Annotated[RiskService, Depends(get_risk_service)],
) -> RoutingService:
    return RoutingService(geo=geo, risk=risk)
