"""
Composition root for standalone batch scripts (no FastAPI request context).

Batch jobs — ingestion, training, scoring — are explicitly out-of-band per
the architecture (24.1: "out-of-band batch jobs for ingestion and the
machine-learning lifecycle"). They build the same services the HTTP API
uses, wired directly against a session, with no HTTP layer or running
server involved.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from safetour.modules.admin.models import SqlAlchemyAuditLogRepository
from safetour.modules.admin.service import AdminService
from safetour.modules.emergency.models import SqlAlchemyCheckInRepository, SqlAlchemyTripShareRepository
from safetour.modules.geo.models import SqlAlchemyGeoReadRepository
from safetour.modules.notifications.models import (
    SqlAlchemyAlertLogRepository,
    SqlAlchemyAlertPreferenceRepository,
    SqlAlchemyPushSubscriptionRepository,
)
from safetour.modules.notifications.service import NotificationsService
from safetour.modules.reports.models import SqlAlchemyCommunityReportRepository, SqlAlchemyReportsSignalAdapter
from safetour.modules.reports.service import ReportsService
from safetour.modules.risk.models import (
    SqlAlchemyCrimeStatisticRepository,
    SqlAlchemyModelRegistry,
    SqlAlchemyPowerStatusRepository,
    SqlAlchemyRiskScoreRepository,
)
from safetour.modules.risk.service import RiskService


def build_risk_service(session: AsyncSession) -> RiskService:
    return RiskService(
        geo=SqlAlchemyGeoReadRepository(session),
        crime_stats=SqlAlchemyCrimeStatisticRepository(session),
        risk_scores=SqlAlchemyRiskScoreRepository(session),
        power=SqlAlchemyPowerStatusRepository(session),
        model_registry=SqlAlchemyModelRegistry(session),
        reports_signal=SqlAlchemyReportsSignalAdapter(session),
    )


def build_reports_service(session: AsyncSession) -> ReportsService:
    return ReportsService(reports=SqlAlchemyCommunityReportRepository(session))


def build_notifications_service(session: AsyncSession) -> NotificationsService:
    return NotificationsService(
        subscriptions=SqlAlchemyPushSubscriptionRepository(session),
        preferences=SqlAlchemyAlertPreferenceRepository(session),
        alert_log=SqlAlchemyAlertLogRepository(session),
    )


def build_admin_service(session: AsyncSession) -> AdminService:
    return AdminService(
        crime_stats=SqlAlchemyCrimeStatisticRepository(session),
        risk=build_risk_service(session),
        reports=build_reports_service(session),
        audit_log=SqlAlchemyAuditLogRepository(session),
        trip_shares=SqlAlchemyTripShareRepository(session),
        checkins=SqlAlchemyCheckInRepository(session),
    )
