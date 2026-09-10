"""Unit tests for risk domain rules: time bands, quality gate (FR-RISK-*, MLR-2)."""

from datetime import time
from uuid import uuid4

from safetour.modules.risk.domain import ModelEvaluation, TimeBand


def test_time_band_boundaries() -> None:
    assert TimeBand.from_time(time(5, 59)) == TimeBand.NIGHT
    assert TimeBand.from_time(time(6, 0)) == TimeBand.MORNING
    assert TimeBand.from_time(time(9, 59)) == TimeBand.MORNING
    assert TimeBand.from_time(time(10, 0)) == TimeBand.MIDDAY
    assert TimeBand.from_time(time(15, 59)) == TimeBand.MIDDAY
    assert TimeBand.from_time(time(16, 0)) == TimeBand.EVENING
    assert TimeBand.from_time(time(19, 59)) == TimeBand.EVENING
    assert TimeBand.from_time(time(20, 0)) == TimeBand.NIGHT


def test_quality_gate_requires_roc_auc_and_pr_auc_above_base_rate() -> None:
    passing = ModelEvaluation(model_version_id=uuid4(), roc_auc=0.82, pr_auc=0.4, base_rate=0.2)
    assert passing.meets_quality_gate()

    low_roc_auc = ModelEvaluation(model_version_id=uuid4(), roc_auc=0.79, pr_auc=0.4, base_rate=0.2)
    assert not low_roc_auc.meets_quality_gate()

    pr_auc_at_base_rate = ModelEvaluation(model_version_id=uuid4(), roc_auc=0.9, pr_auc=0.2, base_rate=0.2)
    assert not pr_auc_at_base_rate.meets_quality_gate()
