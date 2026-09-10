"""Feedback application service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from safetour.modules.feedback.domain import (
    Feedback,
    FeedbackContentRejectedError,
    FeedbackRateLimitedError,
    FeedbackRepository,
    SubjectType,
    contains_blocked_content,
)

_MAX_FEEDBACK_PER_HOUR = 10


@dataclass(slots=True)
class SubmitFeedbackInput:
    user_id: UUID
    subject_type: SubjectType
    subject_id: UUID
    rating: int
    comment: str | None = None


class FeedbackService:
    def __init__(self, feedback: FeedbackRepository) -> None:
        self._feedback = feedback

    async def submit(self, data: SubmitFeedbackInput) -> Feedback:
        recent = await self._feedback.count_recent_by_user(data.user_id, since=datetime.now(UTC) - timedelta(hours=1))
        if recent >= _MAX_FEEDBACK_PER_HOUR:
            raise FeedbackRateLimitedError()
        if contains_blocked_content(data.comment):
            raise FeedbackContentRejectedError()
        feedback = Feedback(
            user_id=data.user_id, subject_type=data.subject_type, subject_id=data.subject_id,
            rating=data.rating, comment=data.comment,
        )
        return await self._feedback.add(feedback)
