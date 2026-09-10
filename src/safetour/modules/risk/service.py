"""
Risk application service.

``RiskService.lookup``/``heatmap`` first try a precomputed, promoted
``RiskScore`` (the fast path: NFR-PERF-1's 50ms p95 is only realistic against
an indexed store, never a live recomputation). When no promoted model has
scored a unit yet, ``_naive_fallback`` derives the same shape of answer
directly from normalised crime rates, so the API never has "nothing to say" —
it degrades to a transparent, documented placeholder instead (NFR-REL-2).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from safetour.modules.geo.domain import GeoReadRepository
from safetour.modules.risk.domain import (
    BiasAudit,
    CrimeStatisticRepository,
    ModelEvaluation,
    ModelRegistry,
    ModelVersion,
    PowerStatus,
    PowerStatusRepository,
    PromotionBlockedError,
    ReportsSignalPort,
    RiskBand,
    RiskScore,
    RiskScoreRepository,
    TimeBand,
    UnitType,
)
from safetour.shared.config import settings

_REFERENCE_MAX_RATE_PER_100K = 5000.0
_POWER_OUTAGE_BONUS = 0.10


@dataclass(slots=True)
class RiskLookupOutput:
    unit_id: UUID | None
    unit_type: UnitType
    time_band: TimeBand
    score: float | None
    band: RiskBand
    data_date: str | None
    top_features: list[str]
    source: str  # "promoted_model" | "naive_baseline"


@dataclass(slots=True)
class HeatmapCell:
    precinct_id: UUID
    score: float | None
    band: RiskBand
    data_date: str | None


def _band_for(score: float) -> RiskBand:
    if score <= settings.RISK_BAND_LOW_MAX:
        return RiskBand.LOW
    if score <= settings.RISK_BAND_MEDIUM_MAX:
        return RiskBand.MEDIUM
    return RiskBand.HIGH


class RiskService:
    def __init__(
        self,
        geo: GeoReadRepository,
        crime_stats: CrimeStatisticRepository,
        risk_scores: RiskScoreRepository,
        power: PowerStatusRepository,
        model_registry: ModelRegistry,
        reports_signal: ReportsSignalPort | None = None,
    ) -> None:
        self._geo = geo
        self._crime_stats = crime_stats
        self._risk_scores = risk_scores
        self._power = power
        self._registry = model_registry
        self._reports_signal = reports_signal

    async def lookup(self, lon: float, lat: float, time_band: TimeBand) -> RiskLookupOutput:
        precinct = await self._geo.find_precinct_for_point(lon, lat)
        if precinct is None:
            return RiskLookupOutput(
                unit_id=None,
                unit_type=UnitType.PRECINCT,
                time_band=time_band,
                score=None,
                band=RiskBand.INSUFFICIENT_DATA,
                data_date=None,
                top_features=[],
                source="naive_baseline",
            )

        promoted = await self._registry.get_promoted()
        if promoted is not None:
            precomputed = await self._risk_scores.get_current(precinct.id, UnitType.PRECINCT, time_band)
            if precomputed is not None:
                return RiskLookupOutput(
                    unit_id=precomputed.unit_id,
                    unit_type=precomputed.unit_type,
                    time_band=precomputed.time_band,
                    score=precomputed.score,
                    band=precomputed.band,
                    data_date=precomputed.data_date.isoformat(),
                    top_features=precomputed.top_features,
                    source="promoted_model",
                )

        return await self._naive_fallback(precinct.id)

    async def heatmap(self, time_band: TimeBand) -> list[HeatmapCell]:
        precincts = await self._geo.list_precincts()
        promoted = await self._registry.get_promoted()
        precomputed_by_unit: dict[UUID, RiskScore] = {}
        if promoted is not None:
            scores = await self._risk_scores.list_current_for_units(
                [p.id for p in precincts], UnitType.PRECINCT, time_band
            )
            precomputed_by_unit = {s.unit_id: s for s in scores}

        cells: list[HeatmapCell] = []
        for precinct in precincts:
            precomputed = precomputed_by_unit.get(precinct.id)
            if precomputed is not None:
                cells.append(
                    HeatmapCell(
                        precinct_id=precinct.id,
                        score=precomputed.score,
                        band=precomputed.band,
                        data_date=precomputed.data_date.isoformat(),
                    )
                )
                continue
            fallback = await self._naive_fallback(precinct.id)
            cells.append(
                HeatmapCell(
                    precinct_id=precinct.id, score=fallback.score, band=fallback.band, data_date=fallback.data_date
                )
            )
        return cells

    async def _naive_fallback(self, precinct_id: UUID) -> RiskLookupOutput:
        stats = await self._crime_stats.latest_for_precinct(precinct_id)
        if not stats:
            return RiskLookupOutput(
                unit_id=precinct_id,
                unit_type=UnitType.PRECINCT,
                time_band=TimeBand.MIDDAY,
                score=None,
                band=RiskBand.INSUFFICIENT_DATA,
                data_date=None,
                top_features=[],
                source="naive_baseline",
            )

        total_rate = sum(s.rate_per_100k for s in stats)
        score = min(total_rate / _REFERENCE_MAX_RATE_PER_100K, 1.0)

        power_status = await self._power.get(precinct_id)
        if power_status is not None and power_status.active_outage:
            score = min(score + _POWER_OUTAGE_BONUS, 1.0)

        top_features = [
            s.category for s in sorted(stats, key=lambda s: s.rate_per_100k, reverse=True)[:3]
        ]

        if self._reports_signal is not None:
            adjustment = await self._reports_signal.weighted_adjustment(precinct_id)
            score = min(max(0.9 * score + 0.1 * adjustment, 0.0), 1.0)
            if adjustment > 0:
                top_features.append("community_reports")

        latest_period = await self._crime_stats.latest_period()
        return RiskLookupOutput(
            unit_id=precinct_id,
            unit_type=UnitType.PRECINCT,
            time_band=TimeBand.MIDDAY,
            score=score,
            band=_band_for(score),
            data_date=latest_period,
            top_features=top_features,
            source="naive_baseline",
        )

    async def record_power_status(self, precinct_id: UUID, active_outage: bool, source: str) -> PowerStatus:
        return await self._power.set(PowerStatus(precinct_id=precinct_id, active_outage=active_outage, source=source))

    async def promote_model(self, version_id: UUID) -> ModelVersion:
        """FR-ADM-3 / MLR-2 / MLR-5: block promotion unless the quality gate and
        a completed bias audit both exist — the only enforceable gate right now,
        exercised for real even before a trained model exists."""
        evaluation = await self._registry.get_evaluation(version_id)
        if evaluation is None:
            raise PromotionBlockedError("no evaluation on record")
        if not evaluation.meets_quality_gate():
            raise PromotionBlockedError(
                f"ROC-AUC {evaluation.roc_auc:.3f} / PR-AUC {evaluation.pr_auc:.3f} below quality gate"
            )
        bias_audit = await self._registry.get_bias_audit(version_id)
        if bias_audit is None or not bias_audit.passed:
            raise PromotionBlockedError("no passing bias audit on record")
        return await self._registry.promote(version_id)

    async def register_model_version(self, label: str) -> ModelVersion:
        return await self._registry.add_version(ModelVersion(label=label))

    async def record_evaluation(
        self, version_id: UUID, roc_auc: float, pr_auc: float, base_rate: float
    ) -> ModelEvaluation:
        return await self._registry.add_evaluation(
            ModelEvaluation(model_version_id=version_id, roc_auc=roc_auc, pr_auc=pr_auc, base_rate=base_rate)
        )

    async def record_bias_audit(
        self, version_id: UUID, *, passed: bool, summary: str, findings: dict[str, str]
    ) -> BiasAudit:
        return await self._registry.add_bias_audit(
            BiasAudit(model_version_id=version_id, passed=passed, summary=summary, findings=findings)
        )
