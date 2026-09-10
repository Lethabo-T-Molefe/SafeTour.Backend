"""
Community reports domain (FR-REP-1, FR-REP-3, MLR-7).

Reports describe *places and conditions only* — never individuals (section
22). Confidence starts low and is capped until moderation confirms it,
decays with age, and a rejected report never contributes to risk again.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4


class ReportType(StrEnum):
    HOTSPOT = "hotspot"
    UNSAFE_STOP = "unsafe_stop"
    CLOSURE = "closure"
    SAFE_CORRIDOR = "safe_corridor"
    OTHER = "other"


class ReportStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


_INITIAL_CONFIDENCE = 0.3


@dataclass(slots=True)
class CommunityReport:
    author_id: UUID
    unit_id: UUID
    report_type: ReportType
    description: str
    status: ReportStatus = ReportStatus.PENDING
    confidence: float = _INITIAL_CONFIDENCE
    confirmations: int = 0
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def confirm(self) -> None:
        self.confirmations += 1
        self.confidence = min(self.confidence + 0.2, 1.0)
        if self.confirmations >= 3 and self.status == ReportStatus.PENDING:
            self.status = ReportStatus.VERIFIED

    def moderate(self, *, approve: bool) -> None:
        self.status = ReportStatus.VERIFIED if approve else ReportStatus.REJECTED
        if approve:
            self.confidence = max(self.confidence, 0.7)
        else:
            self.confidence = 0.0

    def weight(self, *, now: datetime, half_life_days: float, unverified_cap: float) -> float:
        if self.status == ReportStatus.REJECTED:
            return 0.0
        age_days = max((now - self.created_at).total_seconds() / 86_400, 0.0)
        decay = 0.5 ** (age_days / half_life_days) if half_life_days > 0 else 1.0
        weight = self.confidence * decay
        if self.status == ReportStatus.PENDING:
            weight = min(weight, unverified_cap)
        return weight


class CommunityReportRepository(Protocol):
    async def add(self, report: CommunityReport) -> CommunityReport: ...
    async def get(self, report_id: UUID) -> CommunityReport | None: ...
    async def list_for_unit(self, unit_id: UUID, *, limit: int = 50) -> list[CommunityReport]: ...
    async def list_pending(self, *, limit: int = 50) -> list[CommunityReport]: ...
    async def update(self, report: CommunityReport) -> CommunityReport: ...
    async def count_recent_by_author(self, author_id: UUID, *, since: datetime) -> int: ...


class ReportNotFoundError(Exception):
    def __init__(self) -> None:
        super().__init__("Report not found")


class ReportRateLimitedError(Exception):
    def __init__(self) -> None:
        super().__init__("Too many reports submitted recently — please try again later")
