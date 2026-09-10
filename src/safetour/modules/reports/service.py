"""Community reports application service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from safetour.modules.reports.domain import (
    CommunityReport,
    CommunityReportRepository,
    ReportNotFoundError,
    ReportRateLimitedError,
    ReportType,
)

_MAX_REPORTS_PER_HOUR = 5


@dataclass(slots=True)
class SubmitReportInput:
    author_id: UUID
    unit_id: UUID
    report_type: ReportType
    description: str


class ReportsService:
    def __init__(self, reports: CommunityReportRepository) -> None:
        self._reports = reports

    async def submit(self, data: SubmitReportInput) -> CommunityReport:
        recent_count = await self._reports.count_recent_by_author(
            data.author_id, since=datetime.now(UTC) - timedelta(hours=1)
        )
        if recent_count >= _MAX_REPORTS_PER_HOUR:
            raise ReportRateLimitedError()
        report = CommunityReport(
            author_id=data.author_id,
            unit_id=data.unit_id,
            report_type=data.report_type,
            description=data.description,
        )
        return await self._reports.add(report)

    async def list_for_unit(self, unit_id: UUID) -> list[CommunityReport]:
        return await self._reports.list_for_unit(unit_id)

    async def list_pending(self, limit: int = 50) -> list[CommunityReport]:
        return await self._reports.list_pending(limit=limit)

    async def confirm(self, report_id: UUID) -> CommunityReport:
        report = await self._reports.get(report_id)
        if report is None:
            raise ReportNotFoundError()
        report.confirm()
        return await self._reports.update(report)

    async def moderate(self, report_id: UUID, *, approve: bool) -> CommunityReport:
        report = await self._reports.get(report_id)
        if report is None:
            raise ReportNotFoundError()
        report.moderate(approve=approve)
        return await self._reports.update(report)
