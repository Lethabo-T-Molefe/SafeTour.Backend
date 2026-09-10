"""
Users domain: the persona/preferences profile (FR-AUTH-3, FR-AUTH-4).

One profile per auth account, referenced by ``user_id`` only — no ORM
relationship back into the ``auth`` module, per the modular-monolith rule
that modules talk to each other only through explicit exports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class Persona(StrEnum):
    COMMUTER = "commuter"
    AT_RISK_INDIVIDUAL = "at_risk_individual"
    DOMESTIC_TRAVELLER = "domestic_traveller"
    INFORMAL_TRADER = "informal_trader"
    GIG_WORKER = "gig_worker"
    NEWCOMER_STUDENT = "newcomer_student"
    INBOUND_VISITOR = "inbound_visitor"
    ADMINISTRATOR = "administrator"


class TransportMode(StrEnum):
    WALKING = "walking"
    MINIBUS_TAXI = "minibus_taxi"
    BUS_RAPID_TRANSIT = "bus_rapid_transit"
    RAIL = "rail"
    E_HAILING = "e_hailing"


@dataclass(slots=True)
class Profile:
    user_id: UUID
    persona: Persona = Persona.DOMESTIC_TRAVELLER
    interests: list[str] = field(default_factory=list)
    transport_modes: list[TransportMode] = field(default_factory=lambda: [TransportMode.WALKING])
    mobility_needs: str | None = None
    heightened_safety: bool = False
    preferred_language: str = "en"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def apply_preferences(
        self,
        *,
        persona: Persona | None = None,
        interests: list[str] | None = None,
        transport_modes: list[TransportMode] | None = None,
        mobility_needs: str | None = None,
        heightened_safety: bool | None = None,
        preferred_language: str | None = None,
    ) -> None:
        if persona is not None:
            self.persona = persona
        if interests is not None:
            self.interests = interests
        if transport_modes is not None:
            self.transport_modes = transport_modes
        if mobility_needs is not None:
            self.mobility_needs = mobility_needs
        if heightened_safety is not None:
            self.heightened_safety = heightened_safety
        if preferred_language is not None:
            self.preferred_language = preferred_language
        self.updated_at = datetime.now(UTC)


class ProfileRepository(Protocol):
    async def get(self, user_id: UUID) -> Profile | None: ...
    async def upsert(self, profile: Profile) -> Profile: ...
    async def delete(self, user_id: UUID) -> None: ...


class ProfileNotFoundError(Exception):
    def __init__(self) -> None:
        super().__init__("No profile exists for this account yet")
