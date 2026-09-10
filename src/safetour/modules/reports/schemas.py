"""Pydantic request/response models for the reports HTTP API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from safetour.modules.reports.domain import ReportStatus, ReportType


class ReportSubmitRequest(BaseModel):
    unit_id: UUID
    report_type: ReportType
    description: str = Field(min_length=1, max_length=1000)


class ReportResponse(BaseModel):
    id: UUID
    unit_id: UUID
    report_type: ReportType
    description: str
    status: ReportStatus
    confidence: float
    confirmations: int
    created_at: datetime


class ModerateReportRequest(BaseModel):
    approve: bool
