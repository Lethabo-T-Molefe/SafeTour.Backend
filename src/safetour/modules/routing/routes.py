"""Routing API route: POST /routes (FR-ROUTE-1)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from safetour.modules.risk.domain import TimeBand
from safetour.modules.routing.dependencies import get_routing_service
from safetour.modules.routing.domain import LonLat
from safetour.modules.routing.schemas import RouteLegResponse, RouteOptionResponse, RoutePlanRequest
from safetour.modules.routing.service import RoutingService

router = APIRouter(prefix="/routes", tags=["routing"])

RoutingServiceDep = Annotated[RoutingService, Depends(get_routing_service)]


@router.post("", response_model=list[RouteOptionResponse])
async def plan_routes(body: RoutePlanRequest, service: RoutingServiceDep) -> list[RouteOptionResponse]:
    time_band = body.time_band if body.time_band is not None else TimeBand.from_time(datetime.now(UTC).time())
    options = await service.plan(
        origin=LonLat(lon=body.origin_lon, lat=body.origin_lat),
        destination=LonLat(lon=body.destination_lon, lat=body.destination_lat),
        mode=body.mode,
        time_band=time_band,
    )
    return [
        RouteOptionResponse(
            label=option.label,
            legs=[
                RouteLegResponse(
                    start_lon=leg.start.lon,
                    start_lat=leg.start.lat,
                    end_lon=leg.end.lon,
                    end_lat=leg.end.lat,
                    mode=leg.mode,
                    distance_m=leg.distance_m,
                    duration_s=leg.duration_s,
                    risk_band=leg.risk_band,
                    is_flagged_high_risk=leg.is_flagged_high_risk,
                )
                for leg in option.legs
            ],
            total_distance_m=option.total_distance_m,
            total_duration_s=option.total_duration_s,
            overall_risk_band=option.overall_risk_band,
            rationale=option.rationale,
        )
        for option in options
    ]
