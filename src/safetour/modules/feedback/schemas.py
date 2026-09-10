from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from safetour.modules.feedback.domain import SubjectType


class FeedbackSubmitRequest(BaseModel):
    subject_type: SubjectType
    subject_id: UUID
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackResponse(BaseModel):
    id: UUID
    subject_type: SubjectType
    subject_id: UUID
    rating: int
    comment: str | None
