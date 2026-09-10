"""
Routing application service.

MVP routing logic (extension point for the real segment-graph shortest-path
engine — 24.1's "segment-graph routing over the risk store"): for taxi/BRT/
rail modes it walks to the nearest rank or stop, rides the mode, then walks
to the destination (this is also exactly where FR-ROUTE-3's "flag higher-risk
legs, including walking to and from a rank or stop" applies); for walking or
e-hailing it is a single direct leg. A second, "lower_risk" option reroutes
any high-risk leg through the nearest known safe point when one exists nearby.
"""

from __future__ import annotations

import math

from safetour.modules.geo.domain import AttractionCategory, GeoReadRepository
from safetour.modules.risk.domain import RiskBand, TimeBand
from safetour.modules.risk.service import RiskService
from safetour.modules.routing.domain import LonLat, RouteLeg, RouteOption, speed_kmh_for_mode

_MODE_STOP_CATEGORY = {
    "minibus_taxi": AttractionCategory.TAXI_RANK,
    "bus_rapid_transit": AttractionCategory.BUS_STOP,
    "rail": AttractionCategory.RAIL_STATION,
}
_STOP_SEARCH_RADIUS_M = 1500.0
_SAFE_POINT_SEARCH_RADIUS_M = 1000.0
_BAND_SEVERITY = {RiskBand.LOW: 1, RiskBand.MEDIUM: 2, RiskBand.HIGH: 3, RiskBand.INSUFFICIENT_DATA: 0}


def _haversine_m(a: LonLat, b: LonLat) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
    d_phi = math.radians(b.lat - a.lat)
    d_lambda = math.radians(b.lon - a.lon)
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def _midpoint(a: LonLat, b: LonLat) -> LonLat:
    return LonLat(lon=(a.lon + b.lon) / 2, lat=(a.lat + b.lat) / 2)


class RoutingService:
    def __init__(self, geo: GeoReadRepository, risk: RiskService) -> None:
        self._geo = geo
        self._risk = risk

    async def plan(self, origin: LonLat, destination: LonLat, mode: str, time_band: TimeBand) -> list[RouteOption]:
        base_legs = await self._build_direct_legs(origin, destination, mode, time_band)
        fastest = self._to_option("fastest", base_legs, "Direct path for the selected mode and time.")

        alt_legs = await self._build_lower_risk_legs(base_legs, time_band)
        rationale = self._lower_risk_rationale(base_legs, alt_legs)
        lower_risk = self._to_option("lower_risk", alt_legs, rationale)

        return [fastest, lower_risk]

    async def _build_direct_legs(
        self, origin: LonLat, destination: LonLat, mode: str, time_band: TimeBand
    ) -> list[RouteLeg]:
        stop_category = _MODE_STOP_CATEGORY.get(mode)
        if stop_category is None:
            return [await self._score_leg(origin, destination, mode, time_band)]

        origin_stops = await self._geo.list_attractions(
            category=stop_category, near=(origin.lon, origin.lat), radius_m=_STOP_SEARCH_RADIUS_M, limit=1
        )
        dest_stops = await self._geo.list_attractions(
            category=stop_category, near=(destination.lon, destination.lat), radius_m=_STOP_SEARCH_RADIUS_M, limit=1
        )
        if not origin_stops or not dest_stops:
            # No known rank/stop nearby yet (sparse seed data) — fall back to a direct leg.
            return [await self._score_leg(origin, destination, mode, time_band)]

        origin_stop = LonLat(lon=origin_stops[0].location.x, lat=origin_stops[0].location.y)
        dest_stop = LonLat(lon=dest_stops[0].location.x, lat=dest_stops[0].location.y)
        return [
            await self._score_leg(origin, origin_stop, "walking", time_band),
            await self._score_leg(origin_stop, dest_stop, mode, time_band),
            await self._score_leg(dest_stop, destination, "walking", time_band),
        ]

    async def _build_lower_risk_legs(self, base_legs: list[RouteLeg], time_band: TimeBand) -> list[RouteLeg]:
        rerouted: list[RouteLeg] = []
        already_rerouted = False
        for leg in base_legs:
            if already_rerouted or not leg.is_flagged_high_risk:
                rerouted.append(leg)
                continue

            mid = _midpoint(leg.start, leg.end)
            safe_points = await self._geo.list_attractions(
                category=AttractionCategory.SAFE_POINT,
                near=(mid.lon, mid.lat),
                radius_m=_SAFE_POINT_SEARCH_RADIUS_M,
                limit=1,
            )
            if not safe_points:
                rerouted.append(leg)
                continue

            waypoint = LonLat(lon=safe_points[0].location.x, lat=safe_points[0].location.y)
            first_half = await self._score_leg(leg.start, waypoint, leg.mode, time_band)
            second_half = await self._score_leg(waypoint, leg.end, leg.mode, time_band)
            rerouted.extend([first_half, second_half])
            already_rerouted = True
        return rerouted

    def _to_option(self, label: str, legs: list[RouteLeg], rationale: str) -> RouteOption:
        overall = max(
            (leg.risk_band for leg in legs), key=lambda b: _BAND_SEVERITY[b], default=RiskBand.INSUFFICIENT_DATA
        )
        return RouteOption(
            label=label,
            legs=legs,
            total_distance_m=sum(leg.distance_m for leg in legs),
            total_duration_s=sum(leg.duration_s for leg in legs),
            overall_risk_band=overall,
            rationale=rationale,
        )

    def _lower_risk_rationale(self, base_legs: list[RouteLeg], alt_legs: list[RouteLeg]) -> str:
        if alt_legs == base_legs:
            if any(leg.is_flagged_high_risk for leg in base_legs):
                return "No lower-risk alternative was found nearby for the flagged leg."
            return "The direct path already avoids high-risk segments for this time band."
        return "Rerouted through a nearby safer point to avoid a flagged high-risk leg."

    async def _score_leg(self, start: LonLat, end: LonLat, mode: str, time_band: TimeBand) -> RouteLeg:
        mid = _midpoint(start, end)
        risk = await self._risk.lookup(mid.lon, mid.lat, time_band)
        distance_m = _haversine_m(start, end)
        speed_kmh = speed_kmh_for_mode(mode)
        duration_s = (distance_m / 1000 / speed_kmh) * 3600 if speed_kmh > 0 else 0.0
        return RouteLeg(
            start=start,
            end=end,
            mode=mode,
            distance_m=distance_m,
            duration_s=duration_s,
            risk_band=risk.band,
            is_flagged_high_risk=risk.band == RiskBand.HIGH,
        )
