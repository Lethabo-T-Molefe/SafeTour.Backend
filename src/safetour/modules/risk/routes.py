"""Risk API routes: GET /risk (FR-RISK-1) and GET /risk/heatmap (FR-RISK-4)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from safetour.modules.risk.dependencies import get_risk_service
from safetour.modules.risk.domain import TimeBand
from safetour.modules.risk.schemas import HeatmapCellResponse, RiskLookupResponse
from safetour.modules.risk.service import RiskService

router = APIRouter(prefix="/risk", tags=["risk"])

RiskServiceDep = Annotated[RiskService, Depends(get_risk_service)]


def _resolve_time_band(time_band: TimeBand | None) -> TimeBand:
    return time_band if time_band is not None else TimeBand.from_time(datetime.now(UTC).time())


@router.get("", response_model=RiskLookupResponse)
async def get_risk(
    service: RiskServiceDep,
    lon: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
    time_band: TimeBand | None = Query(default=None),
) -> RiskLookupResponse:
    result = await service.lookup(lon, lat, _resolve_time_band(time_band))
    return RiskLookupResponse(**result.__dict__)


@router.get("/heatmap", response_model=list[HeatmapCellResponse])
async def get_heatmap(
    service: RiskServiceDep,
    time_band: TimeBand | None = Query(default=None),
) -> list[HeatmapCellResponse]:
    cells = await service.heatmap(_resolve_time_band(time_band))
    return [HeatmapCellResponse(**cell.__dict__) for cell in cells]
