"""Profile application service (FR-AUTH-3/4/5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from safetour.modules.users.domain import Persona, Profile, ProfileRepository, TransportMode


@dataclass(slots=True)
class UpdateProfileInput:
    persona: Persona | None = None
    interests: list[str] | None = None
    transport_modes: list[TransportMode] | None = None
    mobility_needs: str | None = None
    heightened_safety: bool | None = None
    preferred_language: str | None = None


@dataclass(slots=True)
class ExportedUserData:
    profile: dict[str, Any] = field(default_factory=dict)


class ProfileService:
    def __init__(self, profiles: ProfileRepository) -> None:
        self._profiles = profiles

    async def get_or_create(self, user_id: UUID) -> Profile:
        profile = await self._profiles.get(user_id)
        if profile is None:
            profile = Profile(user_id=user_id)
            profile = await self._profiles.upsert(profile)
        return profile

    async def update(self, user_id: UUID, data: UpdateProfileInput) -> Profile:
        profile = await self.get_or_create(user_id)
        profile.apply_preferences(
            persona=data.persona,
            interests=data.interests,
            transport_modes=data.transport_modes,
            mobility_needs=data.mobility_needs,
            heightened_safety=data.heightened_safety,
            preferred_language=data.preferred_language,
        )
        return await self._profiles.upsert(profile)

    async def export(self, user_id: UUID) -> ExportedUserData:
        profile = await self.get_or_create(user_id)
        return ExportedUserData(
            profile={
                "persona": profile.persona.value,
                "interests": profile.interests,
                "transport_modes": [m.value for m in profile.transport_modes],
                "mobility_needs": profile.mobility_needs,
                "heightened_safety": profile.heightened_safety,
                "preferred_language": profile.preferred_language,
                "created_at": profile.created_at.isoformat(),
            }
        )

    async def delete(self, user_id: UUID) -> None:
        await self._profiles.delete(user_id)
