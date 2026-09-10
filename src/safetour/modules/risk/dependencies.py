from typing import Annotated

from fastapi import Depends

from safetour.modules.geo.dependencies import get_geo_repository
from safetour.modules.geo.models import SqlAlchemyGeoReadRepository
from safetour.modules.reports.dependencies import get_reports_signal_port
from safetour.modules.reports.models import SqlAlchemyReportsSignalAdapter
from safetour.modules.risk.models import (
    SqlAlchemyCrimeStatisticRepository,
    SqlAlchemyModelRegistry,
    SqlAlchemyPowerStatusRepository,
    SqlAlchemyRiskScoreRepository,
)
from safetour.modules.risk.service import RiskService
from safetour.shared.dependencies import DbSession


def get_risk_service(
    db: DbSession,
    geo: Annotated[SqlAlchemyGeoReadRepository, Depends(get_geo_repository)],
    reports_signal: Annotated[SqlAlchemyReportsSignalAdapter, Depends(get_reports_signal_port)],
) -> RiskService:
    return RiskService(
        geo=geo,
        crime_stats=SqlAlchemyCrimeStatisticRepository(db),
        risk_scores=SqlAlchemyRiskScoreRepository(db),
        power=SqlAlchemyPowerStatusRepository(db),
        model_registry=SqlAlchemyModelRegistry(db),
        reports_signal=reports_signal,
    )
