"""SQLAlchemy model, repository, and the risk-facing signal adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from safetour.modules.reports.domain import CommunityReport, ReportStatus, ReportType
from safetour.shared.config import settings
from safetour.shared.database import Base


class CommunityReportModel(Base):
    __tablename__ = "community_reports"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    author_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("auth_accounts.id"), index=True, nullable=False
    )
    unit_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    report_type: Mapped[str] = mapped_column(String(24), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=ReportStatus.PENDING.value, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    confirmations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def _to_entity(row: CommunityReportModel) -> CommunityReport:
    return CommunityReport(
        id=row.id,
        author_id=row.author_id,
        unit_id=row.unit_id,
        report_type=ReportType(row.report_type),
        description=row.description,
        status=ReportStatus(row.status),
        confidence=row.confidence,
        confirmations=row.confirmations,
        created_at=row.created_at,
    )


class SqlAlchemyCommunityReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, report: CommunityReport) -> CommunityReport:
        row = CommunityReportModel(
            id=report.id, author_id=report.author_id, unit_id=report.unit_id,
            report_type=report.report_type.value, description=report.description,
            status=report.status.value, confidence=report.confidence, confirmations=report.confirmations,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_entity(row)

    async def get(self, report_id: UUID) -> CommunityReport | None:
        row = await self._session.get(CommunityReportModel, report_id)
        return _to_entity(row) if row else None

    async def list_for_unit(self, unit_id: UUID, *, limit: int = 50) -> list[CommunityReport]:
        result = await self._session.execute(
            select(CommunityReportModel)
            .where(CommunityReportModel.unit_id == unit_id)
            .order_by(CommunityReportModel.created_at.desc())
            .limit(limit)
        )
        return [_to_entity(r) for r in result.scalars().all()]

    async def list_pending(self, *, limit: int = 50) -> list[CommunityReport]:
        result = await self._session.execute(
            select(CommunityReportModel)
            .where(CommunityReportModel.status == ReportStatus.PENDING.value)
            .order_by(CommunityReportModel.created_at.desc())
            .limit(limit)
        )
        return [_to_entity(r) for r in result.scalars().all()]

    async def update(self, report: CommunityReport) -> CommunityReport:
        row = await self._session.get(CommunityReportModel, report.id)
        if row is not None:
            row.status = report.status.value
            row.confidence = report.confidence
            row.confirmations = report.confirmations
            await self._session.flush()
        return report

    async def count_recent_by_author(self, author_id: UUID, *, since: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(CommunityReportModel)
            .where(CommunityReportModel.author_id == author_id, CommunityReportModel.created_at >= since)
        )
        return int(result.scalar_one())


class SqlAlchemyReportsSignalAdapter:
    """Implements ``risk.domain.ReportsSignalPort`` directly against the table,
    so the risk hot path avoids mapping every report to a domain entity."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def weighted_adjustment(self, unit_id: UUID) -> float:
        result = await self._session.execute(
            select(CommunityReportModel)
            .where(CommunityReportModel.unit_id == unit_id, CommunityReportModel.status != ReportStatus.REJECTED.value)
        )
        now = datetime.now(UTC)
        total = 0.0
        for row in result.scalars().all():
            report = _to_entity(row)
            total += report.weight(
                now=now,
                half_life_days=settings.REPORT_DECAY_HALF_LIFE_DAYS,
                unverified_cap=settings.REPORT_UNVERIFIED_MAX_WEIGHT,
            )
        return min(total, 1.0)
