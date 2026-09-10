"""
Risk domain.

MLR-1..MLR-5 describe a promoted, calibrated, time-split-trained model as the
eventual source of ``RiskScore`` rows, written by an offline scoring batch job
(24.3 "Quarterly refresh") and simply read here at request time (24.4
"Precomputed risk scores ... serve reads from an indexed store"). Until a
model is trained and promoted, ``RiskService`` (service.py) computes the same
shape of result from normalised crime rates directly, so the API contract
does not change the day a real model lands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4


class TimeBand(StrEnum):
    MORNING = "morning"  # 06:00-10:00
    MIDDAY = "midday"  # 10:00-16:00
    EVENING = "evening"  # 16:00-20:00
    NIGHT = "night"  # 20:00-06:00

    @classmethod
    def from_time(cls, moment: time) -> TimeBand:
        hour = moment.hour
        if 6 <= hour < 10:
            return cls.MORNING
        if 10 <= hour < 16:
            return cls.MIDDAY
        if 16 <= hour < 20:
            return cls.EVENING
        return cls.NIGHT


class UnitType(StrEnum):
    PRECINCT = "precinct"
    SEGMENT = "segment"


class RiskBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    INSUFFICIENT_DATA = "insufficient_data"  # FR-RISK-3: never silently default low


class ModelStatus(StrEnum):
    TRAINING = "training"
    EVALUATED = "evaluated"
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled_back"
    RETIRED = "retired"


@dataclass(slots=True)
class CrimeStatistic:
    precinct_id: UUID
    category: str
    period: str  # e.g. "2025Q4", matching SAPS quarterly releases
    count: int
    rate_per_100k: float
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class ContextFeature:
    unit_id: UUID
    unit_type: UnitType
    period: str
    features: dict[str, float]
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class PowerStatus:
    precinct_id: UUID
    active_outage: bool
    source: str
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ModelEvaluation:
    model_version_id: UUID
    roc_auc: float
    pr_auc: float
    base_rate: float
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def meets_quality_gate(self) -> bool:
        """MLR-2 / FR-ADM-3: the only gate that may promote a model."""
        return self.roc_auc >= 0.80 and self.pr_auc > self.base_rate


@dataclass(slots=True)
class BiasAudit:
    model_version_id: UUID
    passed: bool
    summary: str
    findings: dict[str, str]
    audited_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ModelVersion:
    label: str
    status: ModelStatus = ModelStatus.TRAINING
    id: UUID = field(default_factory=uuid4)
    trained_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    promoted_at: datetime | None = None


@dataclass(slots=True)
class RiskScore:
    model_version_id: UUID
    unit_id: UUID
    unit_type: UnitType
    time_band: TimeBand
    score: float
    band: RiskBand
    top_features: list[str]
    data_date: date
    id: UUID = field(default_factory=uuid4)
    computed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class CrimeStatisticRepository(Protocol):
    async def add_many(self, stats: list[CrimeStatistic]) -> None: ...
    async def latest_for_precinct(self, precinct_id: UUID) -> list[CrimeStatistic]: ...
    async def latest_period(self) -> str | None: ...


class RiskScoreRepository(Protocol):
    async def upsert_many(self, scores: list[RiskScore]) -> None: ...
    async def get_current(self, unit_id: UUID, unit_type: UnitType, time_band: TimeBand) -> RiskScore | None: ...
    async def list_current_for_units(
        self, unit_ids: list[UUID], unit_type: UnitType, time_band: TimeBand
    ) -> list[RiskScore]: ...


class PowerStatusRepository(Protocol):
    async def get(self, precinct_id: UUID) -> PowerStatus | None: ...
    async def set(self, status: PowerStatus) -> PowerStatus: ...


class ModelRegistry(Protocol):
    async def add_version(self, version: ModelVersion) -> ModelVersion: ...
    async def get_version(self, version_id: UUID) -> ModelVersion | None: ...
    async def get_promoted(self) -> ModelVersion | None: ...
    async def promote(self, version_id: UUID) -> ModelVersion: ...
    async def add_evaluation(self, evaluation: ModelEvaluation) -> ModelEvaluation: ...
    async def get_evaluation(self, version_id: UUID) -> ModelEvaluation | None: ...
    async def add_bias_audit(self, audit: BiasAudit) -> BiasAudit: ...
    async def get_bias_audit(self, version_id: UUID) -> BiasAudit | None: ...


class ReportsSignalPort(Protocol):
    """Loose coupling to the reports module (MLR-7 / FR-RISK-5): risk asks for
    a weighted, decayed adjustment in [0, 1] without knowing how reports are stored."""

    async def weighted_adjustment(self, unit_id: UUID) -> float: ...


class PromotionBlockedError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Model promotion blocked: {reason}")
