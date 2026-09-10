"""Pydantic request/response models for the users (profile) HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from safetour.modules.users.domain import Persona, TransportMode


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    user_id: UUID
    persona: Persona
    interests: list[str]
    transport_modes: list[TransportMode]
    mobility_needs: str | None
    heightened_safety: bool
    preferred_language: str
    updated_at: datetime


class ProfileUpdateRequest(BaseModel):
    persona: Persona | None = None
    interests: list[str] | None = None
    transport_modes: list[TransportMode] | None = None
    mobility_needs: str | None = None
    heightened_safety: bool | None = None
    preferred_language: str | None = None


class ExportedDataResponse(BaseModel):
    profile: dict[str, Any]
