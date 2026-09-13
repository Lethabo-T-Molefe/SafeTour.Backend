"""
Routing application service.

Primary path: build the segment graph for the requested mode and run
Dijkstra twice (``_RISK_WEIGHT`` = 0 for "fastest", > 0 for "lower_risk") —
the real segment-graph engine (24.1). Per-precinct risk is looked up once
per distinct precinct touched by the graph, not per edge.

Fallback path (``_plan_via_heuristic``): when the graph has no connected
path for the requested mode (sparse data, or origin/destination far from any
known segment), degrade to the original straight-line / walk-to-nearest-stop
heuristic so the endpoint still returns two usable options (NFR-REL-2).
"""

from __future__ import annotations

from dataclasses import replace as dataclass_replace
from uuid import UUID

from safetour.modules.geo.domain import AttractionCategory, GeoReadRepository
from safetour.modules.risk.domain import RiskBand, TimeBand
from safetour.modules.risk.service import RiskService, band_for_score
from safetour.modules.routing.domain import LonLat, RouteLeg, RouteOption, speed_kmh_for_mode
from safetour.modules.routing.graph import NodeKey, PathHop, SegmentGraph, haversine_m

_MODE_STOP_CATEGORY = {
    "minibus_taxi": AttractionCategory.TAXI_RANK,
    "bus_rapid_transit": AttractionCategory.BUS_STOP,
    "rail": AttractionCategory.RAIL_STATION,
}
_STOP_SEARCH_RADIUS_M = 1500.0
_SAFE_POINT_SEARCH_RADIUS_M = 1000.0
_BAND_SEVERITY = {RiskBand.LOW: 1, RiskBand.MEDIUM: 2, RiskBand.HIGH: 3, RiskBand.INSUFFICIENT_DATA: 0}
_CONNECTOR_MODE = "walking"
_RISK_WEIGHT = 3.0  # how strongly the "lower_risk" search trades distance for safety
_MIN_CONNECTOR_LEG_M = 5.0  # skip a walking connector leg shorter than this


def _midpoint(a: LonLat, b: LonLat) -> LonLat:
    return LonLat(lon=(a.lon + b.lon) / 2, lat=(a.lat + b.lat) / 2)


def _duration_s(distance_m: float, mode: str) -> float:
    speed_kmh = speed_kmh_for_mode(mode)
    return (distance_m / 1000 / speed_kmh) * 3600 if speed_kmh > 0 else 0.0


class RoutingService:
    def __init__(self, geo: GeoReadRepository, risk: RiskService) -> None:
        self._geo = geo
        self._risk = risk

    async def plan(self, origin: LonLat, destination: LonLat, mode: str, time_band: TimeBand) -> list[RouteOption]:
        segments = await self._geo.list_all_segments(mode=mode)
        graph = SegmentGraph(segments)

        graph_options = None
        if not graph.is_empty():
            graph_options = await self._plan_via_graph(graph, origin, destination, mode, time_band)
        if graph_options is not None:
            return graph_options

        return await self._plan_via_heuristic(origin, destination, mode, time_band)

    # ---- graph-based planning (the real engine) ----------------------------------

    async def _plan_via_graph(
        self, graph: SegmentGraph, origin: LonLat, destination: LonLat, mode: str, time_band: TimeBand
    ) -> list[RouteOption] | None:
        start_node = graph.nearest_node(origin, mode=mode)
        goal_node = graph.nearest_node(destination, mode=mode)
        if start_node is None or goal_node is None:
            return None

        precinct_risk = await self._precompute_precinct_risk(graph, time_band)

        fastest_hops = graph.shortest_path(
            start_node, goal_node, mode=mode, precinct_risk=precinct_risk, risk_weight=0.0
        )
        lower_risk_hops = graph.shortest_path(
            start_node, goal_node, mode=mode, precinct_risk=precinct_risk, risk_weight=_RISK_WEIGHT
        )
        if fastest_hops is None or lower_risk_hops is None:
            return None

        fastest = self._graph_hops_to_option(
            "fastest", origin, destination, graph, start_node, goal_node, fastest_hops, mode, precinct_risk,
            "Shortest known path for the selected mode and time band.",
        )
        lower_risk = self._graph_hops_to_option(
            "lower_risk", origin, destination, graph, start_node, goal_node, lower_risk_hops, mode, precinct_risk, "",
        )
        rationale = (
            "The shortest path already minimises risk for this time band."
            if fastest_hops == lower_risk_hops
            else "Reweighted the known network to favour lower-risk precincts, trading some distance for safety."
        )
        lower_risk = dataclass_replace(lower_risk, rationale=rationale)
        return [fastest, lower_risk]

    def _graph_hops_to_option(
        self, label: str, origin: LonLat, destination: LonLat, graph: SegmentGraph, start_node: NodeKey,
        goal_node: NodeKey, hops: list[PathHop], mode: str, precinct_risk: dict[UUID, float], rationale: str,
    ) -> RouteOption:
        legs: list[RouteLeg] = []

        start_point = graph.node_point(start_node)
        connector_in = haversine_m(origin, start_point)
        if connector_in > _MIN_CONNECTOR_LEG_M:
            legs.append(self._plain_leg(origin, start_point, _CONNECTOR_MODE))

        for hop in hops:
            band = band_for_score(precinct_risk.get(hop.precinct_id, 0.5))
            legs.append(
                RouteLeg(
                    start=hop.start, end=hop.end, mode=mode, distance_m=hop.distance_m,
                    duration_s=_duration_s(hop.distance_m, mode), risk_band=band,
                    is_flagged_high_risk=band == RiskBand.HIGH, segment_id=hop.segment_id,
                )
            )

        goal_point = graph.node_point(goal_node)
        connector_out = haversine_m(goal_point, destination)
        if connector_out > _MIN_CONNECTOR_LEG_M:
            legs.append(self._plain_leg(goal_point, destination, _CONNECTOR_MODE))

        return self._to_option(label, legs, rationale)

    def _plain_leg(self, start: LonLat, end: LonLat, mode: str) -> RouteLeg:
        """A connector leg outside the known graph (origin/destination to the
        nearest graph node) — risk there is genuinely unknown, not assumed low."""
        distance_m = haversine_m(start, end)
        return RouteLeg(
            start=start, end=end, mode=mode, distance_m=distance_m, duration_s=_duration_s(distance_m, mode),
            risk_band=RiskBand.INSUFFICIENT_DATA, is_flagged_high_risk=False,
        )

    async def _precompute_precinct_risk(self, graph: SegmentGraph, time_band: TimeBand) -> dict[UUID, float]:
        precinct_risk: dict[UUID, float] = {}
        for precinct_id in graph.distinct_precinct_ids():
            precinct = await self._geo.get_precinct(precinct_id)
            if precinct is None:
                continue
            centroid = precinct.boundary.centroid
            result = await self._risk.lookup(centroid.x, centroid.y, time_band)
            precinct_risk[precinct_id] = result.score if result.score is not None else 0.5
        return precinct_risk

    # ---- heuristic fallback (sparse/disconnected graph) ---------------------------

    async def _plan_via_heuristic(
        self, origin: LonLat, destination: LonLat, mode: str, time_band: TimeBand
    ) -> list[RouteOption]:
        base_legs = await self._build_direct_legs(origin, destination, mode, time_band)
        fastest = self._to_option(
            "fastest", base_legs, "Direct path for the selected mode and time (no connected segment graph nearby)."
        )

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
        distance_m = haversine_m(start, end)
        return RouteLeg(
            start=start,
            end=end,
            mode=mode,
            distance_m=distance_m,
            duration_s=_duration_s(distance_m, mode),
            risk_band=risk.band,
            is_flagged_high_risk=risk.band == RiskBand.HIGH,
        )
