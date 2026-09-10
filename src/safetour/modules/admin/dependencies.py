from typing import Annotated

from fastapi import Depends

from safetour.modules.admin.models import SqlAlchemyAuditLogRepository
from safetour.modules.admin.service import AdminService
from safetour.modules.emergency.models import (
    SqlAlchemyCheckInRepository,
    SqlAlchemyTripShareRepository,
)
from safetour.modules.reports.dependencies import get_reports_service
from safetour.modules.reports.service import ReportsService
from safetour.modules.risk.dependencies import get_risk_service
from safetour.modules.risk.models import SqlAlchemyCrimeStatisticRepository
from safetour.modules.risk.service import RiskService
from safetour.shared.dependencies import DbSession


def get_admin_service(
    db: DbSession,
    risk: Annotated[RiskService, Depends(get_risk_service)],
    reports: Annotated[ReportsService, Depends(get_reports_service)],
) -> AdminService:
    return AdminService(
        crime_stats=SqlAlchemyCrimeStatisticRepository(db),
        risk=risk,
        reports=reports,
        audit_log=SqlAlchemyAuditLogRepository(db),
        trip_shares=SqlAlchemyTripShareRepository(db),
        checkins=SqlAlchemyCheckInRepository(db),
    )
