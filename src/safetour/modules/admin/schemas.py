"""Pydantic request/response models for the admin HTTP API (FR-ADM-*)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IngestRowRequest(BaseModel):
    precinct_id: UUID
    category: str
    count: int = Field(ge=0)
    rate_per_100k: float = Field(ge=0)


class IngestRequest(BaseModel):
    period: str = Field(examples=["2025Q4"])
    rows: list[IngestRowRequest]


class IngestResponse(BaseModel):
    period: str
    rows_ingested: int


class RetrainRequest(BaseModel):
    label: str


class ModelVersionResponse(BaseModel):
    id: UUID
    label: str
    status: str
    trained_at: datetime
    promoted_at: datetime | None


class EvaluationRequest(BaseModel):
    roc_auc: float = Field(ge=0, le=1)
    pr_auc: float = Field(ge=0, le=1)
    base_rate: float = Field(ge=0, le=1)


class EvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_version_id: UUID
    roc_auc: float
    pr_auc: float
    base_rate: float
    evaluated_at: datetime


class BiasAuditRequest(BaseModel):
    passed: bool
    summary: str
    findings: dict[str, str] = Field(default_factory=dict)


class BiasAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_version_id: UUID
    passed: bool
    summary: str
    findings: dict[str, str]
    audited_at: datetime


class ModerateReportRequest(BaseModel):
    approve: bool


class AuditLogEntryResponse(BaseModel):
    id: UUID
    actor_id: UUID
    action: str
    subject_type: str
    subject_id: str
    detail: dict[str, str]
    created_at: datetime


class PurgeResultResponse(BaseModel):
    trip_shares: int
    checkins: int


class PowerStatusRequest(BaseModel):
    precinct_id: UUID
    active_outage: bool
    source: str = "manual"


class PowerStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    precinct_id: UUID
    active_outage: bool
    source: str
    recorded_at: datetime
