"""SQLAlchemy models and repository implementations for the risk module."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    ARRAY,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from safetour.modules.risk.domain import (
    BiasAudit,
    CrimeStatistic,
    ModelEvaluation,
    ModelStatus,
    ModelVersion,
    PowerStatus,
    RiskBand,
    RiskScore,
    TimeBand,
    UnitType,
)
from safetour.shared.database import Base


class CrimeStatisticModel(Base):
    __tablename__ = "crime_statistics"
    __table_args__ = (
        UniqueConstraint("precinct_id", "category", "period", name="uq_crime_statistics_unit_category_period"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    precinct_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    period: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_per_100k: Mapped[float] = mapped_column(Float, nullable=False)


class ContextFeatureModel(Base):
    __tablename__ = "context_features"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    unit_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    unit_type: Mapped[str] = mapped_column(String(16), nullable=False)
    period: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    features: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False)


class PowerStatusModel(Base):
    __tablename__ = "power_statuses"

    precinct_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    active_outage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ModelVersionModel(Base):
    __tablename__ = "model_versions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=ModelStatus.TRAINING.value, nullable=False)
    trained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModelEvaluationModel(Base):
    __tablename__ = "model_evaluations"

    model_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("model_versions.id", ondelete="CASCADE"), primary_key=True
    )
    roc_auc: Mapped[float] = mapped_column(Float, nullable=False)
    pr_auc: Mapped[float] = mapped_column(Float, nullable=False)
    base_rate: Mapped[float] = mapped_column(Float, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BiasAuditModel(Base):
    __tablename__ = "bias_audits"

    model_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("model_versions.id", ondelete="CASCADE"), primary_key=True
    )
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    findings: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    audited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RiskScoreModel(Base):
    __tablename__ = "risk_scores"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    model_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("model_versions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    unit_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    unit_type: Mapped[str] = mapped_column(String(16), nullable=False)
    time_band: Mapped[str] = mapped_column(String(16), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    band: Mapped[str] = mapped_column(String(24), nullable=False)
    top_features: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    data_date: Mapped[date] = mapped_column(Date, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SqlAlchemyCrimeStatisticRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_many(self, stats: list[CrimeStatistic]) -> None:
        """Upsert on (precinct_id, category, period) — FR-ADM-1: ingestion must
        be idempotent, so re-running the same quarter's file is a no-op update
        rather than a pile of duplicate rows."""
        if not stats:
            return
        stmt = pg_insert(CrimeStatisticModel).values(
            [
                {
                    "id": stat.id,
                    "precinct_id": stat.precinct_id,
                    "category": stat.category,
                    "period": stat.period,
                    "count": stat.count,
                    "rate_per_100k": stat.rate_per_100k,
                }
                for stat in stats
            ]
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_crime_statistics_unit_category_period",
            set_={"count": stmt.excluded.count, "rate_per_100k": stmt.excluded.rate_per_100k},
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def latest_for_precinct(self, precinct_id: UUID) -> list[CrimeStatistic]:
        latest_period_result = await self._session.execute(
            select(func.max(CrimeStatisticModel.period)).where(CrimeStatisticModel.precinct_id == precinct_id)
        )
        latest_period = latest_period_result.scalar_one_or_none()
        if latest_period is None:
            return []
        result = await self._session.execute(
            select(CrimeStatisticModel).where(
                CrimeStatisticModel.precinct_id == precinct_id,
                CrimeStatisticModel.period == latest_period,
            )
        )
        return [
            CrimeStatistic(
                id=r.id, precinct_id=r.precinct_id, category=r.category, period=r.period,
                count=r.count, rate_per_100k=r.rate_per_100k,
            )
            for r in result.scalars().all()
        ]

    async def latest_period(self) -> str | None:
        result = await self._session.execute(select(func.max(CrimeStatisticModel.period)))
        return result.scalar_one_or_none()


class SqlAlchemyRiskScoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, scores: list[RiskScore]) -> None:
        for score in scores:
            self._session.add(
                RiskScoreModel(
                    id=score.id,
                    model_version_id=score.model_version_id,
                    unit_id=score.unit_id,
                    unit_type=score.unit_type.value,
                    time_band=score.time_band.value,
                    score=score.score,
                    band=score.band.value,
                    top_features=score.top_features,
                    data_date=score.data_date,
                )
            )
        await self._session.flush()

    async def get_current(self, unit_id: UUID, unit_type: UnitType, time_band: TimeBand) -> RiskScore | None:
        result = await self._session.execute(
            select(RiskScoreModel)
            .where(
                RiskScoreModel.unit_id == unit_id,
                RiskScoreModel.unit_type == unit_type.value,
                RiskScoreModel.time_band == time_band.value,
            )
            .order_by(RiskScoreModel.computed_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return _score_entity(row) if row else None

    async def list_current_for_units(
        self, unit_ids: list[UUID], unit_type: UnitType, time_band: TimeBand
    ) -> list[RiskScore]:
        if not unit_ids:
            return []
        result = await self._session.execute(
            select(RiskScoreModel)
            .where(
                RiskScoreModel.unit_id.in_(unit_ids),
                RiskScoreModel.unit_type == unit_type.value,
                RiskScoreModel.time_band == time_band.value,
            )
            .order_by(RiskScoreModel.computed_at.desc())
        )
        seen: dict[UUID, RiskScore] = {}
        for row in result.scalars().all():
            if row.unit_id not in seen:
                seen[row.unit_id] = _score_entity(row)
        return list(seen.values())


def _score_entity(row: RiskScoreModel) -> RiskScore:
    return RiskScore(
        id=row.id,
        model_version_id=row.model_version_id,
        unit_id=row.unit_id,
        unit_type=UnitType(row.unit_type),
        time_band=TimeBand(row.time_band),
        score=row.score,
        band=RiskBand(row.band),
        top_features=list(row.top_features),
        data_date=row.data_date,
        computed_at=row.computed_at,
    )


class SqlAlchemyPowerStatusRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, precinct_id: UUID) -> PowerStatus | None:
        row = await self._session.get(PowerStatusModel, precinct_id)
        if row is None:
            return None
        return PowerStatus(
            precinct_id=row.precinct_id, active_outage=row.active_outage, source=row.source,
            recorded_at=row.recorded_at,
        )

    async def set(self, status: PowerStatus) -> PowerStatus:
        row = await self._session.get(PowerStatusModel, status.precinct_id)
        if row is None:
            row = PowerStatusModel(precinct_id=status.precinct_id)
            self._session.add(row)
        row.active_outage = status.active_outage
        row.source = status.source
        await self._session.flush()
        return status


class SqlAlchemyModelRegistry:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_version(self, version: ModelVersion) -> ModelVersion:
        row = ModelVersionModel(id=version.id, label=version.label, status=version.status.value)
        self._session.add(row)
        await self._session.flush()
        return version

    async def get_version(self, version_id: UUID) -> ModelVersion | None:
        row = await self._session.get(ModelVersionModel, version_id)
        return _version_entity(row) if row else None

    async def get_promoted(self) -> ModelVersion | None:
        result = await self._session.execute(
            select(ModelVersionModel)
            .where(ModelVersionModel.status == ModelStatus.PROMOTED.value)
            .order_by(ModelVersionModel.promoted_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return _version_entity(row) if row else None

    async def promote(self, version_id: UUID) -> ModelVersion:
        # Exactly one promoted version at a time (section 25): demote any
        # currently-promoted version, then flip the pointer — an O(1) rollback.
        result = await self._session.execute(
            select(ModelVersionModel).where(ModelVersionModel.status == ModelStatus.PROMOTED.value)
        )
        for currently_promoted in result.scalars().all():
            currently_promoted.status = ModelStatus.RETIRED.value

        row = await self._session.get(ModelVersionModel, version_id)
        if row is None:
            raise ValueError("Unknown model version")
        row.status = ModelStatus.PROMOTED.value
        row.promoted_at = func.now()
        await self._session.flush()
        await self._session.refresh(row)
        return _version_entity(row)

    async def add_evaluation(self, evaluation: ModelEvaluation) -> ModelEvaluation:
        row = ModelEvaluationModel(
            model_version_id=evaluation.model_version_id,
            roc_auc=evaluation.roc_auc,
            pr_auc=evaluation.pr_auc,
            base_rate=evaluation.base_rate,
        )
        self._session.add(row)
        await self._session.flush()
        return evaluation

    async def get_evaluation(self, version_id: UUID) -> ModelEvaluation | None:
        row = await self._session.get(ModelEvaluationModel, version_id)
        if row is None:
            return None
        return ModelEvaluation(
            model_version_id=row.model_version_id, roc_auc=row.roc_auc, pr_auc=row.pr_auc,
            base_rate=row.base_rate, evaluated_at=row.evaluated_at,
        )

    async def add_bias_audit(self, audit: BiasAudit) -> BiasAudit:
        row = BiasAuditModel(
            model_version_id=audit.model_version_id, passed=audit.passed, summary=audit.summary,
            findings=audit.findings,
        )
        self._session.add(row)
        await self._session.flush()
        return audit

    async def get_bias_audit(self, version_id: UUID) -> BiasAudit | None:
        row = await self._session.get(BiasAuditModel, version_id)
        if row is None:
            return None
        return BiasAudit(
            model_version_id=row.model_version_id, passed=row.passed, summary=row.summary,
            findings=row.findings, audited_at=row.audited_at,
        )


def _version_entity(row: ModelVersionModel) -> ModelVersion:
    return ModelVersion(
        id=row.id, label=row.label, status=ModelStatus(row.status), trained_at=row.trained_at,
        promoted_at=row.promoted_at,
    )
