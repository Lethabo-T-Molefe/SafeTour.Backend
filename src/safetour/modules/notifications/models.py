"""SQLAlchemy models and repositories for the notifications module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from safetour.modules.notifications.domain import AlertLogEntry, AlertPreference, PushSubscription
from safetour.shared.database import Base


class PushSubscriptionModel(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("auth_accounts.id"), index=True, nullable=False
    )
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    keys: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AlertPreferenceModel(Base):
    __tablename__ = "alert_preferences"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    safety_alerts_opt_in: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    non_safety_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AlertLogModel(Base):
    __tablename__ = "alert_log"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SqlAlchemyPushSubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, subscription: PushSubscription) -> PushSubscription:
        row = PushSubscriptionModel(
            id=subscription.id, user_id=subscription.user_id, endpoint=subscription.endpoint, keys=subscription.keys
        )
        self._session.add(row)
        await self._session.flush()
        return subscription

    async def list_for_user(self, user_id: UUID) -> list[PushSubscription]:
        result = await self._session.execute(
            select(PushSubscriptionModel).where(PushSubscriptionModel.user_id == user_id)
        )
        return [
            PushSubscription(id=r.id, user_id=r.user_id, endpoint=r.endpoint, keys=r.keys, created_at=r.created_at)
            for r in result.scalars().all()
        ]


class SqlAlchemyAlertPreferenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID) -> AlertPreference | None:
        row = await self._session.get(AlertPreferenceModel, user_id)
        if row is None:
            return None
        return AlertPreference(
            user_id=row.user_id, safety_alerts_opt_in=row.safety_alerts_opt_in, non_safety_opt_in=row.non_safety_opt_in
        )

    async def upsert(self, preference: AlertPreference) -> AlertPreference:
        row = await self._session.get(AlertPreferenceModel, preference.user_id)
        if row is None:
            row = AlertPreferenceModel(user_id=preference.user_id)
            self._session.add(row)
        row.safety_alerts_opt_in = preference.safety_alerts_opt_in
        row.non_safety_opt_in = preference.non_safety_opt_in
        await self._session.flush()
        return preference


class SqlAlchemyAlertLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: AlertLogEntry) -> AlertLogEntry:
        row = AlertLogModel(id=entry.id, recipient=entry.recipient, channel=entry.channel, message=entry.message)
        self._session.add(row)
        await self._session.flush()
        return entry

    async def list_recent(self, *, limit: int = 50) -> list[AlertLogEntry]:
        result = await self._session.execute(
            select(AlertLogModel).order_by(AlertLogModel.created_at.desc()).limit(limit)
        )
        return [
            AlertLogEntry(id=r.id, recipient=r.recipient, channel=r.channel, message=r.message, created_at=r.created_at)
            for r in result.scalars().all()
        ]
