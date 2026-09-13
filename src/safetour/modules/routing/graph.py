"""
Segment-graph shortest-path routing (24.1: "segment-graph routing over the
risk store"). This is the real routing engine promised as an extension point
in the initial scaffold: nodes are segment endpoints (snapped to ~1m so
touching segments share a node), edges are segment spans weighted by
distance and, for the "lower_risk" pass, by the risk of the precinct the
segment sits in. Two independent Dijkstra runs (risk_weight=0 vs >0) give
the two required route options (FR-ROUTE-1).

Per-edge risk is precomputed once per distinct precinct before the search
runs, so the search itself is synchronous, in-memory graph traversal —
no per-edge database round trips (NFR-PERF-2's four-second budget would not
survive that).
"""

from __future__ import annotations

import heapq
import math
from collections import defaultdict
from collections.abc import KeysView, Sequence
from dataclasses import dataclass
from uuid import UUID

from safetour.modules.geo.domain import Segment
from safetour.modules.routing.domain import LonLat

_NODE_PRECISION = 5  # ~1.1m at the equator: snaps coincident endpoints into one node
NodeKey = tuple[float, float]


def _node_key(lon: float, lat: float) -> NodeKey:
    return (round(lon, _NODE_PRECISION), round(lat, _NODE_PRECISION))


def haversine_m(a: LonLat, b: LonLat) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
    d_phi = math.radians(b.lat - a.lat)
    d_lambda = math.radians(b.lon - a.lon)
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


@dataclass(slots=True)
class GraphEdge:
    segment_id: UUID
    to_node: NodeKey
    distance_m: float
    modes: list[str]
    precinct_id: UUID


@dataclass(slots=True)
class PathHop:
    segment_id: UUID
    start: LonLat
    end: LonLat
    distance_m: float
    precinct_id: UUID


class SegmentGraph:
    def __init__(self, segments: Sequence[Segment]) -> None:
        self._nodes: dict[NodeKey, LonLat] = {}
        self._adjacency: dict[NodeKey, list[GraphEdge]] = defaultdict(list)
        for segment in segments:
            coords = list(segment.geometry.coords)
            for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:], strict=False):
                key1, key2 = _node_key(lon1, lat1), _node_key(lon2, lat2)
                self._nodes[key1] = LonLat(lon=lon1, lat=lat1)
                self._nodes[key2] = LonLat(lon=lon2, lat=lat2)
                distance = haversine_m(LonLat(lon1, lat1), LonLat(lon2, lat2))
                self._adjacency[key1].append(GraphEdge(segment.id, key2, distance, segment.modes, segment.precinct_id))
                self._adjacency[key2].append(GraphEdge(segment.id, key1, distance, segment.modes, segment.precinct_id))

    def is_empty(self) -> bool:
        return not self._nodes

    def node_point(self, key: NodeKey) -> LonLat:
        return self._nodes[key]

    def distinct_precinct_ids(self) -> set[UUID]:
        return {edge.precinct_id for edges in self._adjacency.values() for edge in edges}

    def nearest_node(self, point: LonLat, *, mode: str | None = None) -> NodeKey | None:
        candidate_keys: set[NodeKey] | KeysView[NodeKey]
        if mode is not None:
            candidate_keys = {
                key for key, edges in self._adjacency.items() if any(mode in edge.modes for edge in edges)
            }
        else:
            candidate_keys = self._nodes.keys()
        if not candidate_keys:
            return None
        return min(candidate_keys, key=lambda key: haversine_m(point, self._nodes[key]))

    def shortest_path(
        self, start: NodeKey, goal: NodeKey, *, mode: str, precinct_risk: dict[UUID, float], risk_weight: float
    ) -> list[PathHop] | None:
        """Dijkstra over edges tagged with ``mode``. Returns ``None`` if no path exists."""
        if start == goal:
            return []

        distances: dict[NodeKey, float] = {start: 0.0}
        # came_from[node] = (previous_node, edge_used_to_arrive_here)
        came_from: dict[NodeKey, tuple[NodeKey, GraphEdge]] = {}
        visited: set[NodeKey] = set()
        queue: list[tuple[float, NodeKey]] = [(0.0, start)]

        while queue:
            cost, node = heapq.heappop(queue)
            if node in visited:
                continue
            visited.add(node)
            if node == goal:
                break
            for edge in self._adjacency.get(node, []):
                if mode not in edge.modes:
                    continue
                risk = precinct_risk.get(edge.precinct_id, 0.5)
                new_cost = cost + edge.distance_m * (1 + risk_weight * risk)
                if new_cost < distances.get(edge.to_node, math.inf):
                    distances[edge.to_node] = new_cost
                    came_from[edge.to_node] = (node, edge)
                    heapq.heappush(queue, (new_cost, edge.to_node))

        if goal not in distances:
            return None

        reversed_hops: list[PathHop] = []
        node = goal
        while node != start:
            previous_node, edge = came_from[node]
            reversed_hops.append(
                PathHop(
                    segment_id=edge.segment_id,
                    start=self._nodes[previous_node],
                    end=self._nodes[node],
                    distance_m=edge.distance_m,
                    precinct_id=edge.precinct_id,
                )
            )
            node = previous_node
        reversed_hops.reverse()
        return reversed_hops
