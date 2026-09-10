"""Admin domain: the audit log (FR-ADM-4 — every administrative action is logged)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4


@dataclass(slots=True)
class AuditLogEntry:
    actor_id: UUID
    action: str
    subject_type: str
    subject_id: str
    detail: dict[str, str]
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AuditLogRepository(Protocol):
    async def add(self, entry: AuditLogEntry) -> AuditLogEntry: ...
    async def list_recent(self, *, limit: int = 100) -> list[AuditLogEntry]: ...


class InvalidIngestRowError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid crime statistic row: {reason}")
