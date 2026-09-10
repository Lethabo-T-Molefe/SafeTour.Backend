"""
Admin application service.

Orchestrates the other modules' own services rather than reaching into their
persistence — the one place in the codebase allowed to depend on many
modules at once, since it *is* the composition point for the model
lifecycle and moderation (24.2 "administration").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from safetour.modules.admin.domain import AuditLogEntry, AuditLogRepository, InvalidIngestRowError
from safetour.modules.emergency.domain import CheckInRepository, TripShareRepository
from safetour.modules.reports.domain import CommunityReport
from safetour.modules.reports.service import ReportsService
from safetour.modules.risk.domain import (
    BiasAudit,
    CrimeStatistic,
    CrimeStatisticRepository,
    ModelEvaluation,
    ModelVersion,
)
from safetour.modules.risk.service import RiskService


@dataclass(slots=True)
class IngestRow:
    precinct_id: UUID
    category: str
    count: int
    rate_per_100k: float


class AdminService:
    def __init__(
        self,
        crime_stats: CrimeStatisticRepository,
        risk: RiskService,
        reports: ReportsService,
        audit_log: AuditLogRepository,
        trip_shares: TripShareRepository,
        checkins: CheckInRepository,
    ) -> None:
        self._crime_stats = crime_stats
        self._risk = risk
        self._reports = reports
        self._audit_log = audit_log
        self._trip_shares = trip_shares
        self._checkins = checkins

    async def ingest_crime_statistics(self, actor_id: UUID, period: str, rows: list[IngestRow]) -> int:
        for row in rows:
            if row.count < 0 or row.rate_per_100k < 0:
                raise InvalidIngestRowError(f"negative value for precinct {row.precinct_id}")
        stats = [
            CrimeStatistic(
                precinct_id=r.precinct_id, category=r.category, period=period,
                count=r.count, rate_per_100k=r.rate_per_100k,
            )
            for r in rows
        ]
        await self._crime_stats.add_many(stats)
        await self._log(actor_id, "ingest_crime_statistics", "period", period, {"rows": str(len(rows))})
        return len(rows)

    async def trigger_retrain(self, actor_id: UUID, label: str) -> ModelVersion:
        """Registers a pending model version. The actual training run happens
        offline (Colab/Kaggle, per the tech stack) — an operator later calls
        ``record_evaluation``/``record_bias_audit`` with its results."""
        version = await self._risk.register_model_version(label)
        await self._log(actor_id, "trigger_retrain", "model_version", str(version.id), {"label": label})
        return version

    async def record_evaluation(
        self, actor_id: UUID, version_id: UUID, roc_auc: float, pr_auc: float, base_rate: float
    ) -> ModelEvaluation:
        evaluation = await self._risk.record_evaluation(version_id, roc_auc, pr_auc, base_rate)
        await self._log(
            actor_id, "record_evaluation", "model_version", str(version_id),
            {"roc_auc": f"{roc_auc:.3f}", "pr_auc": f"{pr_auc:.3f}"},
        )
        return evaluation

    async def record_bias_audit(
        self, actor_id: UUID, version_id: UUID, passed: bool, summary: str, findings: dict[str, str]
    ) -> BiasAudit:
        audit = await self._risk.record_bias_audit(version_id, passed=passed, summary=summary, findings=findings)
        await self._log(actor_id, "record_bias_audit", "model_version", str(version_id), {"passed": str(passed)})
        return audit

    async def promote_model(self, actor_id: UUID, version_id: UUID) -> ModelVersion:
        version = await self._risk.promote_model(version_id)  # raises PromotionBlockedError if the gate fails
        await self._log(actor_id, "promote_model", "model_version", str(version_id), {"label": version.label})
        return version

    async def moderate_report(self, actor_id: UUID, report_id: UUID, approve: bool) -> CommunityReport:
        report = await self._reports.moderate(report_id, approve=approve)
        await self._log(actor_id, "moderate_report", "report", str(report_id), {"approved": str(approve)})
        return report

    async def list_pending_reports(self, limit: int = 50) -> list[CommunityReport]:
        return await self._reports.list_pending(limit)

    async def list_audit_log(self, limit: int = 100) -> list[AuditLogEntry]:
        return await self._audit_log.list_recent(limit=limit)

    async def purge_expired_emergency_data(self, actor_id: UUID) -> dict[str, int]:
        """NFR-PRIV-2: live-location/check-in data is transient — this is the
        batch job (24.2 "data purging") that actually removes it once expired,
        rather than the application layer merely hiding it."""
        now = datetime.now(UTC)
        purged_shares = await self._trip_shares.purge_expired(before=now)
        purged_checkins = await self._checkins.purge_expired(before=now)
        result = {"trip_shares": purged_shares, "checkins": purged_checkins}
        await self._log(
            actor_id, "purge_expired_emergency_data", "batch_job", "purge",
            {k: str(v) for k, v in result.items()},
        )
        return result

    async def _log(
        self, actor_id: UUID, action: str, subject_type: str, subject_id: str, detail: dict[str, str]
    ) -> None:
        await self._audit_log.add(
            AuditLogEntry(
                actor_id=actor_id, action=action, subject_type=subject_type,
                subject_id=subject_id, detail=detail,
            )
        )
