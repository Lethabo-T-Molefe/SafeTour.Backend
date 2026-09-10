from safetour.modules.feedback.models import SqlAlchemyFeedbackRepository
from safetour.modules.feedback.service import FeedbackService
from safetour.shared.dependencies import DbSession


def get_feedback_service(db: DbSession) -> FeedbackService:
    return FeedbackService(feedback=SqlAlchemyFeedbackRepository(db))
