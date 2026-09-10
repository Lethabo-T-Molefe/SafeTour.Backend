from safetour.modules.reports.models import (
    SqlAlchemyCommunityReportRepository,
    SqlAlchemyReportsSignalAdapter,
)
from safetour.modules.reports.service import ReportsService
from safetour.shared.dependencies import DbSession


def get_reports_service(db: DbSession) -> ReportsService:
    return ReportsService(reports=SqlAlchemyCommunityReportRepository(db))


def get_reports_signal_port(db: DbSession) -> SqlAlchemyReportsSignalAdapter:
    return SqlAlchemyReportsSignalAdapter(db)
