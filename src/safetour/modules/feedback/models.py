"""SQLAlchemy model and repository for feedback."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from safetour.modules.feedback.domain import Feedback
from safetour.shared.database import Base


class FeedbackModel(Base):
    __tablename__ = "feedback"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("auth_accounts.id"), index=True, nullable=False
    )
    subject_type: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SqlAlchemyFeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, feedback: Feedback) -> Feedback:
        row = FeedbackModel(
            id=feedback.id, user_id=feedback.user_id, subject_type=feedback.subject_type.value,
            subject_id=feedback.subject_id, rating=feedback.rating, comment=feedback.comment,
        )
        self._session.add(row)
        await self._session.flush()
        return feedback

    async def count_recent_by_user(self, user_id: UUID, *, since: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(FeedbackModel)
            .where(FeedbackModel.user_id == user_id, FeedbackModel.created_at >= since)
        )
        return int(result.scalar_one())
