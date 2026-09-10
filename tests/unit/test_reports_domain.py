"""Unit tests for community-report weighting and decay (FR-REP-3, MLR-7)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from safetour.modules.reports.domain import CommunityReport, ReportStatus, ReportType


def _report(
    status: ReportStatus = ReportStatus.PENDING, confidence: float = 0.3, age_days: float = 0
) -> CommunityReport:
    return CommunityReport(
        author_id=uuid4(),
        unit_id=uuid4(),
        report_type=ReportType.HOTSPOT,
        description="test",
        status=status,
        confidence=confidence,
        created_at=datetime.now(UTC) - timedelta(days=age_days),
    )


def test_rejected_report_has_zero_weight() -> None:
    report = _report(status=ReportStatus.REJECTED, confidence=1.0)
    assert report.weight(now=datetime.now(UTC), half_life_days=14, unverified_cap=0.15) == 0.0


def test_pending_report_weight_is_capped() -> None:
    report = _report(status=ReportStatus.PENDING, confidence=1.0, age_days=0)
    weight = report.weight(now=datetime.now(UTC), half_life_days=14, unverified_cap=0.15)
    assert weight <= 0.15


def test_verified_report_is_not_capped_but_still_decays() -> None:
    fresh = _report(status=ReportStatus.VERIFIED, confidence=0.8, age_days=0)
    old = _report(status=ReportStatus.VERIFIED, confidence=0.8, age_days=14)
    now = datetime.now(UTC)
    fresh_weight = fresh.weight(now=now, half_life_days=14, unverified_cap=0.15)
    old_weight = old.weight(now=now, half_life_days=14, unverified_cap=0.15)
    assert fresh_weight > 0.15
    assert old_weight == pytest.approx(fresh_weight / 2, rel=1e-3)


def test_three_confirmations_auto_verifies_a_pending_report() -> None:
    report = _report(status=ReportStatus.PENDING)
    report.confirm()
    report.confirm()
    assert report.status == ReportStatus.PENDING
    report.confirm()
    assert report.status == ReportStatus.VERIFIED


def test_moderation_reject_zeroes_confidence() -> None:
    report = _report(status=ReportStatus.PENDING, confidence=0.9)
    report.moderate(approve=False)
    assert report.status == ReportStatus.REJECTED
    assert report.confidence == 0.0
