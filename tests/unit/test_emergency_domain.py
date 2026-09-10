"""Unit tests for emergency domain rules (FR-EMG-2/3, NFR-PRIV-4)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from safetour.modules.emergency.domain import CheckIn, ShareChannel, TripShare


def test_checkin_is_overdue_only_after_expected_time_with_no_confirmation() -> None:
    checkin = CheckIn(
        trip_id=uuid4(), expected_arrival_at=datetime.now(UTC) + timedelta(hours=1), contact_ref="0821234567"
    )
    assert not checkin.is_overdue()

    overdue = CheckIn(
        trip_id=uuid4(), expected_arrival_at=datetime.now(UTC) - timedelta(minutes=1), contact_ref="0821234567"
    )
    assert overdue.is_overdue()


def test_confirming_a_checkin_clears_overdue_state() -> None:
    checkin = CheckIn(
        trip_id=uuid4(), expected_arrival_at=datetime.now(UTC) - timedelta(minutes=1), contact_ref="0821234567"
    )
    assert checkin.is_overdue()
    checkin.confirm()
    assert not checkin.is_overdue()


def test_trip_share_is_active_only_before_expiry_and_when_not_revoked() -> None:
    share = TripShare(
        trip_id=uuid4(), contact_name="Mom", channel=ShareChannel.SMS, contact_address="0821234567",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert share.is_active()

    share.revoked_at = datetime.now(UTC)
    assert not share.is_active()


def test_expired_trip_share_is_not_active() -> None:
    share = TripShare(
        trip_id=uuid4(), contact_name="Mom", channel=ShareChannel.SMS, contact_address="0821234567",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    assert not share.is_active()
