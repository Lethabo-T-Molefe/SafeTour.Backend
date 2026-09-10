"""Feedback domain (FR-FDBK-1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

_BLOCKED_WORDS = {"kill", "hate", "stupid"}  # placeholder content filter — swap for a real moderation service


class SubjectType(StrEnum):
    ROUTE = "route"
    ITINERARY = "itinerary"
    REPORT = "report"


@dataclass(slots=True)
class Feedback:
    user_id: UUID
    subject_type: SubjectType
    subject_id: UUID
    rating: int
    comment: str | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def contains_blocked_content(comment: str | None) -> bool:
    if not comment:
        return False
    words = set(comment.lower().split())
    return bool(words & _BLOCKED_WORDS)


class FeedbackRepository(Protocol):
    async def add(self, feedback: Feedback) -> Feedback: ...
    async def count_recent_by_user(self, user_id: UUID, *, since: datetime) -> int: ...


class FeedbackRateLimitedError(Exception):
    def __init__(self) -> None:
        super().__init__("Too much feedback submitted recently — please try again later")


class FeedbackContentRejectedError(Exception):
    def __init__(self) -> None:
        super().__init__("Comment rejected by the content filter")
