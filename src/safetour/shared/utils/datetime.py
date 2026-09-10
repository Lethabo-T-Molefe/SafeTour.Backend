"""Timezone-aware datetime helpers."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """
    Return the current UTC time as a timezone-aware ``datetime``.

    Prefer this over ``datetime.utcnow()`` (naive) so comparisons and DB
    round-trips do not silently drop tzinfo.
    """
    return datetime.now(UTC)
