"""Feedback API route: POST /feedback (FR-FDBK-1)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from safetour.modules.auth.dependencies import CurrentAccountId
from safetour.modules.feedback.dependencies import get_feedback_service
from safetour.modules.feedback.schemas import FeedbackResponse, FeedbackSubmitRequest
from safetour.modules.feedback.service import FeedbackService, SubmitFeedbackInput

router = APIRouter(prefix="/feedback", tags=["feedback"])

FeedbackServiceDep = Annotated[FeedbackService, Depends(get_feedback_service)]


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    account_id: CurrentAccountId, body: FeedbackSubmitRequest, service: FeedbackServiceDep
) -> FeedbackResponse:
    feedback = await service.submit(
        SubmitFeedbackInput(
            user_id=account_id, subject_type=body.subject_type, subject_id=body.subject_id,
            rating=body.rating, comment=body.comment,
        )
    )
    return FeedbackResponse.model_validate(feedback, from_attributes=True)
