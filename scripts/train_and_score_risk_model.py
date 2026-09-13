"""
Quarterly risk-model training and scoring batch job (24.3's "Quarterly
refresh": ingest, rebuild features, train, evaluate, audit for bias, score
all units, and promote by pointer). Runs out-of-band against the database
directly — no running API server needed, matching the architecture's
"Model training: Google Colab or Kaggle notebooks" (this script is what
would run there).

Implements every MLR requirement against whatever crime_statistics rows are
in the database (scripts/seed_data.py's synthetic data, or real ingested
data — the pipeline does not care which):

  MLR-1  Time-based split, most recent labelled period held out. No random
         splits.
  MLR-2  Promotion blocked unless ROC-AUC >= 0.80 and PR-AUC > base rate —
         enforced by the SAME ``RiskService.promote_model`` gate the
         ``/admin/models/{v}/promote`` endpoint uses. If a run does not
         clear the bar, that is reported plainly and nothing is promoted —
         this script never overrides the gate.
  MLR-3  Calibration via ``CalibratedClassifierCV``, skipped (documented,
         not silently faked) when there is too little training data for a
         stable cross-validated calibration.
  MLR-4  Global feature importances are stored as each scored row's
         ``top_features`` — an explicit simplification of true per-instance
         attribution (e.g. SHAP), noted here rather than overstated.
  MLR-5  A bias check: correlation between predicted risk and precinct
         population, so the model is not silently just learning "bigger
         population -> higher risk" (NFR-ETH-2 requires normalised-rate
         reasoning, not population proxies).

Label: for each (precinct, period) with a following period available,
1 if that following period's total rate exceeds the cross-sectional median
for that period, else 0. The most recent period has no "next" period and is
therefore never a training/holdout row — it is exactly the row scored for
current serving.

Usage:
    uv run python scripts/train_and_score_risk_model.py
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import joblib
import numpy as np
import pandas as pd
from geoalchemy2.shape import to_shape
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).parent))
from _composition import build_notifications_service, build_risk_service  # noqa: E402

from safetour.modules.geo.models import PrecinctModel  # noqa: E402
from safetour.modules.risk.domain import PromotionBlockedError, RiskScore, TimeBand, UnitType  # noqa: E402
from safetour.modules.risk.models import CrimeStatisticModel, SqlAlchemyRiskScoreRepository  # noqa: E402
from safetour.modules.risk.service import RiskService, band_for_score  # noqa: E402
from safetour.shared.database import AsyncSessionLocal  # noqa: E402

_MIN_ROWS_FOR_CALIBRATION = 30
_MODEL_DIR = Path(__file__).parent / "models"
_TIME_BAND_ADJUSTMENT = {TimeBand.MORNING: 0.0, TimeBand.MIDDAY: 0.0, TimeBand.EVENING: 0.02, TimeBand.NIGHT: 0.05}
_BIAS_CORRELATION_THRESHOLD = 0.6


def _period_sort_key(period: str) -> tuple[int, int]:
    year, quarter = period.split("Q")
    return int(year), int(quarter)


@dataclass(slots=True)
class TrainingResult:
    model: object
    feature_names: list[str]
    roc_auc: float
    pr_auc: float
    base_rate: float
    bias_correlation: float
    bias_passed: bool


def _load_crime_frame(stats_rows: list[CrimeStatisticModel], populations: dict[UUID, int]) -> pd.DataFrame:
    raw = pd.DataFrame(
        [
            {"precinct_id": r.precinct_id, "category": r.category, "period": r.period, "rate": r.rate_per_100k}
            for r in stats_rows
        ]
    )
    if raw.empty:
        return raw
    pivot = raw.pivot_table(
        index=["precinct_id", "period"], columns="category", values="rate", aggfunc="sum"
    ).reset_index()
    # A precinct missing a category for a given period (real ingested data need
    # not have identical categories every quarter) counts as a zero rate there,
    # not a gap that would otherwise poison every downstream feature with NaN.
    category_cols = [c for c in pivot.columns if c not in {"precinct_id", "period"}]
    pivot[category_cols] = pivot[category_cols].fillna(0.0)
    pivot["total_rate"] = pivot[category_cols].sum(axis=1)
    pivot["population"] = pivot["precinct_id"].map(populations)
    pivot["period_order"] = pivot["period"].map(_period_sort_key)
    return pivot.sort_values(["precinct_id", "period_order"]).reset_index(drop=True)


def _build_features_and_labels(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    frame = frame.copy()
    frame["lag_total_rate"] = frame.groupby("precinct_id")["total_rate"].shift(1)
    frame["next_total_rate"] = frame.groupby("precinct_id")["total_rate"].shift(-1)
    frame["next_period"] = frame.groupby("precinct_id")["period"].shift(-1)

    next_median_by_period = frame["next_period"].map(frame.groupby("period")["total_rate"].median())
    frame["label"] = (frame["next_total_rate"] > next_median_by_period).astype("Int64")
    frame.loc[frame["next_total_rate"].isna(), "label"] = pd.NA

    category_columns = [c for c in frame.columns if c not in {
        "precinct_id", "period", "period_order", "total_rate", "population", "lag_total_rate",
        "next_total_rate", "next_period", "label",
    }]
    feature_names = ["total_rate", "population", "lag_total_rate", *category_columns]
    frame = frame.dropna(subset=["lag_total_rate", "population"]).reset_index(drop=True)
    return frame, feature_names


async def main() -> None:
    async with AsyncSessionLocal() as session:
        stats_result = await session.execute(select(CrimeStatisticModel))
        stats_rows = list(stats_result.scalars().all())
        precinct_result = await session.execute(select(PrecinctModel))
        precincts = list(precinct_result.scalars().all())
        populations = {p.id: (p.population or 0) for p in precincts}

        if not stats_rows:
            print("No crime_statistics rows found — run scripts/seed_data.py or ingest_saps_csv.py first.")
            return

        frame = _load_crime_frame(stats_rows, populations)
        frame, feature_names = _build_features_and_labels(frame)

        current_period = frame["period"].map(_period_sort_key).max()
        current_rows = frame[frame["period_order"] == current_period]
        labelled = frame[frame["label"].notna()].copy()
        labelled["label"] = labelled["label"].astype(int)

        if labelled["period"].nunique() < 2:
            print(
                "Need at least two labelled periods (three total quarters) for a time-based split — "
                "not enough data yet."
            )
            return

        holdout_period = labelled["period_order"].max()
        train_frame = labelled[labelled["period_order"] < holdout_period]
        test_frame = labelled[labelled["period_order"] == holdout_period]

        if train_frame["label"].nunique() < 2 or test_frame["label"].nunique() < 2:
            print("Training or holdout split has only one class present — cannot compute ROC-AUC/PR-AUC meaningfully.")
            return

        result = _train(train_frame, test_frame, feature_names)
        print(
            f"Time-split holdout ({labelled.loc[labelled['period_order'] == holdout_period, 'period'].iloc[0]}): "
            f"ROC-AUC={result.roc_auc:.3f}  PR-AUC={result.pr_auc:.3f}  base rate={result.base_rate:.3f}"
        )
        print(
            f"Bias check: |corr(predicted risk, population)| = {result.bias_correlation:.3f} "
            f"-> passed={result.bias_passed}"
        )

        _MODEL_DIR.mkdir(exist_ok=True)
        model_path = _MODEL_DIR / f"risk_model_{datetime.now(UTC):%Y%m%dT%H%M%S}.joblib"
        joblib.dump({"model": result.model, "feature_names": result.feature_names}, model_path)
        print(f"Saved model artifact to {model_path}")

        risk_service = build_risk_service(session)
        precincts_by_id = {p.id: p for p in precincts}
        old_bands = await _current_bands(risk_service, current_rows, precincts_by_id)

        version = await risk_service.register_model_version(f"rf-{datetime.now(UTC):%Y%m%dT%H%M%S}")
        await risk_service.record_evaluation(version.id, result.roc_auc, result.pr_auc, result.base_rate)
        await risk_service.record_bias_audit(
            version.id, passed=result.bias_passed,
            summary=f"Correlation between predicted risk and precinct population is {result.bias_correlation:.3f}.",
            findings={"population_correlation": f"{result.bias_correlation:.3f}"},
        )

        await _score_current_period(session, version.id, current_rows, result)
        await session.commit()

        try:
            promoted = await risk_service.promote_model(version.id)
            await session.commit()
            print(f"Promoted model version {promoted.label}.")
        except PromotionBlockedError as exc:
            print(
                f"Not promoted: {exc}. "
                "Risk lookups keep using the previous promoted version (or the naive fallback)."
            )

        new_bands = await _current_bands(risk_service, current_rows, precincts_by_id)
        await _alert_on_band_changes(session, old_bands, new_bands)
        await session.commit()


def _train(train_frame: pd.DataFrame, test_frame: pd.DataFrame, feature_names: list[str]) -> TrainingResult:
    x_train = train_frame[feature_names].to_numpy()
    y_train = train_frame["label"].to_numpy()
    x_test = test_frame[feature_names].to_numpy()
    y_test = test_frame["label"].to_numpy()

    base_model = RandomForestClassifier(n_estimators=200, random_state=42, class_weight="balanced")

    if len(x_train) >= _MIN_ROWS_FOR_CALIBRATION:
        model = CalibratedClassifierCV(base_model, method="sigmoid", cv=3)
        model.fit(x_train, y_train)
    else:
        print(
            f"Only {len(x_train)} training rows (< {_MIN_ROWS_FOR_CALIBRATION}) — skipping CalibratedClassifierCV "
            "and using the raw forest's probabilities (MLR-3 nominal on this data volume)."
        )
        model = base_model
        model.fit(x_train, y_train)

    proba_test = model.predict_proba(x_test)[:, 1]
    roc_auc = float(roc_auc_score(y_test, proba_test))
    pr_auc = float(average_precision_score(y_test, proba_test))
    base_rate = float(y_test.mean())

    all_labelled_x = np.vstack([x_train, x_test])
    all_proba = model.predict_proba(all_labelled_x)[:, 1]
    all_population = np.concatenate([train_frame["population"].to_numpy(), test_frame["population"].to_numpy()])
    bias_correlation = float(np.corrcoef(all_proba, all_population)[0, 1]) if len(set(all_population)) > 1 else 0.0
    bias_passed = abs(bias_correlation) <= _BIAS_CORRELATION_THRESHOLD

    return TrainingResult(
        model=model, feature_names=feature_names, roc_auc=roc_auc, pr_auc=pr_auc, base_rate=base_rate,
        bias_correlation=bias_correlation, bias_passed=bias_passed,
    )


async def _current_bands(
    risk_service: RiskService, current_rows: pd.DataFrame, precincts_by_id: dict[UUID, PrecinctModel]
) -> dict[UUID, str]:
    """What each precinct's midday band reads as *right now* — via the same
    ``RiskService.lookup`` the API uses, so this reflects whatever is
    actually promoted (or the naive fallback), not this run's in-memory
    prediction. Called both before and after promotion to detect a change."""
    bands: dict[UUID, str] = {}
    for precinct_id in current_rows["precinct_id"].unique():
        precinct = precincts_by_id.get(precinct_id)
        if precinct is None:
            continue
        centroid = to_shape(precinct.boundary).centroid
        result = await risk_service.lookup(centroid.x, centroid.y, TimeBand.MIDDAY)
        bands[precinct_id] = result.band.value
    return bands


async def _alert_on_band_changes(session: AsyncSession, old_bands: dict[UUID, str], new_bands: dict[UUID, str]) -> None:
    """24.3's 'Quarterly refresh: ... then diff bands and alert affected
    users.' Scope note: this logs one system-level alert per precinct whose
    band changed (visible via the alert log) rather than resolving to
    individual users' push endpoints — no push provider is actually wired up
    yet (see notifications/service.py), so a per-user fan-out would be
    theatre without a real delivery channel behind it."""
    notifications = build_notifications_service(session)
    changed = {pid: (old_bands.get(pid), new_bands[pid]) for pid in new_bands if old_bands.get(pid) != new_bands[pid]}
    for precinct_id, (old_band, new_band) in changed.items():
        await notifications.send_alert(
            recipient=f"precinct:{precinct_id}",
            channel="system",
            message=f"Risk band changed from {old_band or 'unscored'} to {new_band} for this precinct.",
        )
    if changed:
        print(f"Band changed for {len(changed)} precinct(s) — logged to the alert log.")
    else:
        print("No band changes since the previous promoted version.")


async def _score_current_period(
    session: AsyncSession, version_id: UUID, current_rows: pd.DataFrame, result: TrainingResult
) -> None:
    if current_rows.empty:
        print("No current-period rows to score.")
        return

    x_current = current_rows[result.feature_names].to_numpy()
    proba = result.model.predict_proba(x_current)[:, 1]

    importances = _global_feature_importances(result.model, result.feature_names)
    data_date = current_rows["period"].iloc[0]

    scores: list[RiskScore] = []
    for (_idx, row), base_score in zip(current_rows.iterrows(), proba, strict=True):
        for time_band, adjustment in _TIME_BAND_ADJUSTMENT.items():
            score = min(float(base_score) + adjustment, 1.0)
            scores.append(
                RiskScore(
                    model_version_id=version_id, unit_id=row["precinct_id"], unit_type=UnitType.PRECINCT,
                    time_band=time_band, score=score, band=band_for_score(score), top_features=importances,
                    data_date=date.today() if not isinstance(data_date, str) else _period_to_date(data_date),
                )
            )
    await SqlAlchemyRiskScoreRepository(session).upsert_many(scores)
    print(f"Scored {len(current_rows)} precincts x {len(_TIME_BAND_ADJUSTMENT)} time bands for period {data_date}.")


def _period_to_date(period: str) -> date:
    year, quarter = period.split("Q")
    month = (int(quarter) - 1) * 3 + 1
    return date(int(year), month, 1)


def _global_feature_importances(model: object, feature_names: list[str]) -> list[str]:
    # ``model.estimator`` on a fitted CalibratedClassifierCV is still the
    # *unfitted* prototype passed to its constructor — the fitted forest
    # (with real feature_importances_) only lives on each fold's
    # calibrated_classifiers_[i].estimator.
    if hasattr(model, "calibrated_classifiers_"):
        estimator = model.calibrated_classifiers_[0].estimator
    else:
        estimator = model
    importances = getattr(estimator, "feature_importances_", None)
    if importances is None:
        return []
    ranked = sorted(zip(feature_names, importances, strict=True), key=lambda pair: pair[1], reverse=True)
    return [name for name, _importance in ranked[:3]]


if __name__ == "__main__":
    asyncio.run(main())
