"""Admin API routes (FR-ADM-*) — every route requires CurrentAdminId."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from safetour.modules.admin.dependencies import get_admin_service
from safetour.modules.admin.schemas import (
    AuditLogEntryResponse,
    BiasAuditRequest,
    BiasAuditResponse,
    EvaluationRequest,
    EvaluationResponse,
    IngestRequest,
    IngestResponse,
    ModelVersionResponse,
    ModerateReportRequest,
    PurgeResultResponse,
    RetrainRequest,
)
from safetour.modules.admin.service import AdminService, IngestRow
from safetour.modules.auth.dependencies import CurrentAdminId
from safetour.modules.reports.schemas import ReportResponse

router = APIRouter(prefix="/admin", tags=["admin"])

AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]


@router.post("/ingest", response_model=IngestResponse)
async def ingest(admin_id: CurrentAdminId, body: IngestRequest, service: AdminServiceDep) -> IngestResponse:
    rows = [
        IngestRow(precinct_id=r.precinct_id, category=r.category, count=r.count, rate_per_100k=r.rate_per_100k)
        for r in body.rows
    ]
    count = await service.ingest_crime_statistics(admin_id, body.period, rows)
    return IngestResponse(period=body.period, rows_ingested=count)


@router.post("/retrain", response_model=ModelVersionResponse)
async def retrain(admin_id: CurrentAdminId, body: RetrainRequest, service: AdminServiceDep) -> ModelVersionResponse:
    version = await service.trigger_retrain(admin_id, body.label)
    return ModelVersionResponse.model_validate(version, from_attributes=True)


@router.post("/models/{version_id}/evaluation", response_model=EvaluationResponse)
async def record_evaluation(
    version_id: UUID, admin_id: CurrentAdminId, body: EvaluationRequest, service: AdminServiceDep
) -> EvaluationResponse:
    evaluation = await service.record_evaluation(admin_id, version_id, body.roc_auc, body.pr_auc, body.base_rate)
    return EvaluationResponse.model_validate(evaluation, from_attributes=True)


@router.post("/models/{version_id}/bias-audit", response_model=BiasAuditResponse)
async def record_bias_audit(
    version_id: UUID, admin_id: CurrentAdminId, body: BiasAuditRequest, service: AdminServiceDep
) -> BiasAuditResponse:
    audit = await service.record_bias_audit(admin_id, version_id, body.passed, body.summary, body.findings)
    return BiasAuditResponse.model_validate(audit, from_attributes=True)


@router.post("/models/{version_id}/promote", response_model=ModelVersionResponse)
async def promote(version_id: UUID, admin_id: CurrentAdminId, service: AdminServiceDep) -> ModelVersionResponse:
    version = await service.promote_model(admin_id, version_id)
    return ModelVersionResponse.model_validate(version, from_attributes=True)


@router.get("/reports/pending", response_model=list[ReportResponse])
async def list_pending_reports(
    admin_id: CurrentAdminId, service: AdminServiceDep, limit: int = Query(default=50, ge=1, le=200)
) -> list[ReportResponse]:
    reports = await service.list_pending_reports(limit)
    return [ReportResponse.model_validate(r, from_attributes=True) for r in reports]


@router.post("/reports/{report_id}/moderate", response_model=ReportResponse)
async def moderate_report(
    report_id: UUID, admin_id: CurrentAdminId, body: ModerateReportRequest, service: AdminServiceDep
) -> ReportResponse:
    report = await service.moderate_report(admin_id, report_id, body.approve)
    return ReportResponse.model_validate(report, from_attributes=True)


@router.get("/audit-log", response_model=list[AuditLogEntryResponse])
async def audit_log(
    admin_id: CurrentAdminId, service: AdminServiceDep, limit: int = Query(default=100, ge=1, le=500)
) -> list[AuditLogEntryResponse]:
    entries = await service.list_audit_log(limit=limit)
    return [AuditLogEntryResponse.model_validate(e, from_attributes=True) for e in entries]


@router.post("/purge-expired", response_model=PurgeResultResponse)
async def purge_expired(admin_id: CurrentAdminId, service: AdminServiceDep) -> PurgeResultResponse:
    result = await service.purge_expired_emergency_data(admin_id)
    return PurgeResultResponse(**result)
