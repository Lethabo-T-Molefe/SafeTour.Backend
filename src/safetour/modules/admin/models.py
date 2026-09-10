"""SQLAlchemy model and repository for the audit log."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from safetour.modules.admin.domain import AuditLogEntry
from safetour.shared.database import Base


class AuditLogModel(Base):
    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SqlAlchemyAuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: AuditLogEntry) -> AuditLogEntry:
        row = AuditLogModel(
            id=entry.id, actor_id=entry.actor_id, action=entry.action, subject_type=entry.subject_type,
            subject_id=entry.subject_id, detail=entry.detail,
        )
        self._session.add(row)
        await self._session.flush()
        return entry

    async def list_recent(self, *, limit: int = 100) -> list[AuditLogEntry]:
        result = await self._session.execute(
            select(AuditLogModel).order_by(AuditLogModel.created_at.desc()).limit(limit)
        )
        return [
            AuditLogEntry(
                id=r.id, actor_id=r.actor_id, action=r.action, subject_type=r.subject_type,
                subject_id=r.subject_id, detail=r.detail, created_at=r.created_at,
            )
            for r in result.scalars().all()
        ]
