"""Reports API routes (FR-REP-1, FR-REP-3)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from safetour.modules.auth.dependencies import CurrentAccountId
from safetour.modules.reports.dependencies import get_reports_service
from safetour.modules.reports.schemas import ReportResponse, ReportSubmitRequest
from safetour.modules.reports.service import ReportsService, SubmitReportInput

router = APIRouter(prefix="/reports", tags=["reports"])

ReportsServiceDep = Annotated[ReportsService, Depends(get_reports_service)]


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def submit_report(
    account_id: CurrentAccountId, body: ReportSubmitRequest, service: ReportsServiceDep
) -> ReportResponse:
    report = await service.submit(
        SubmitReportInput(
            author_id=account_id, unit_id=body.unit_id, report_type=body.report_type, description=body.description
        )
    )
    return ReportResponse.model_validate(report, from_attributes=True)


@router.get("", response_model=list[ReportResponse])
async def list_reports(service: ReportsServiceDep, unit_id: UUID = Query(...)) -> list[ReportResponse]:
    reports = await service.list_for_unit(unit_id)
    return [ReportResponse.model_validate(r, from_attributes=True) for r in reports]


@router.post("/{report_id}/confirm", response_model=ReportResponse)
async def confirm_report(
    report_id: UUID, _account_id: CurrentAccountId, service: ReportsServiceDep
) -> ReportResponse:
    report = await service.confirm(report_id)
    return ReportResponse.model_validate(report, from_attributes=True)
