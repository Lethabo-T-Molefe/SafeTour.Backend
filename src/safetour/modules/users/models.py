"""SQLAlchemy model and repository for profiles."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ARRAY, Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from safetour.modules.users.domain import Persona, Profile, TransportMode
from safetour.shared.database import Base


class ProfileModel(Base):
    __tablename__ = "profiles"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    persona: Mapped[str] = mapped_column(String(32), default=Persona.DOMESTIC_TRAVELLER.value, nullable=False)
    interests: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    transport_modes: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=lambda: [TransportMode.WALKING.value], nullable=False
    )
    mobility_needs: Mapped[str | None] = mapped_column(String(500), nullable=True)
    heightened_safety: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def _to_entity(row: ProfileModel) -> Profile:
    return Profile(
        user_id=row.user_id,
        persona=Persona(row.persona),
        interests=list(row.interests),
        transport_modes=[TransportMode(m) for m in row.transport_modes],
        mobility_needs=row.mobility_needs,
        heightened_safety=row.heightened_safety,
        preferred_language=row.preferred_language,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID) -> Profile | None:
        row = await self._session.get(ProfileModel, user_id)
        return _to_entity(row) if row else None

    async def upsert(self, profile: Profile) -> Profile:
        row = await self._session.get(ProfileModel, profile.user_id)
        if row is None:
            row = ProfileModel(user_id=profile.user_id)
            self._session.add(row)
        row.persona = profile.persona.value
        row.interests = profile.interests
        row.transport_modes = [m.value for m in profile.transport_modes]
        row.mobility_needs = profile.mobility_needs
        row.heightened_safety = profile.heightened_safety
        row.preferred_language = profile.preferred_language
        await self._session.flush()
        return _to_entity(row)

    async def delete(self, user_id: UUID) -> None:
        row = await self._session.get(ProfileModel, user_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()
