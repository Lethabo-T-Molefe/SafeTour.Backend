"""Unit tests for the segment-graph Dijkstra router (FR-ROUTE-1/2)."""

from uuid import UUID, uuid4

from shapely.geometry import LineString

from safetour.modules.geo.domain import Segment
from safetour.modules.routing.domain import LonLat
from safetour.modules.routing.graph import SegmentGraph, haversine_m

# A diamond: A -> B -> D (~480m total) sits in a high-risk precinct;
# A -> C -> D (~570m total) is a little longer but sits in a low-risk
# precinct — close enough that a risk weight of 10 clearly flips the choice,
# while a risk weight of 0 unambiguously prefers the shorter (riskier) path.
_A, _B, _D, _C = (28.000, -25.000), (28.002, -25.000), (28.002, -25.0025), (28.000, -25.0032)


def _segment(coords: tuple[tuple[float, float], tuple[float, float]], precinct_id: UUID) -> Segment:
    return Segment(id=uuid4(), precinct_id=precinct_id, geometry=LineString(coords), modes=["walking"])


def _build_diamond_graph() -> tuple[SegmentGraph, UUID, UUID]:
    high_risk_precinct = uuid4()
    low_risk_precinct = uuid4()
    segments = [
        _segment((_A, _B), high_risk_precinct),
        _segment((_B, _D), high_risk_precinct),
        _segment((_A, _C), low_risk_precinct),
        _segment((_C, _D), low_risk_precinct),
    ]
    return SegmentGraph(segments), high_risk_precinct, low_risk_precinct


def test_haversine_distance_zero_for_same_point() -> None:
    point = LonLat(lon=28.1881, lat=-25.7461)
    assert haversine_m(point, point) == 0.0


def test_shortest_path_ignores_risk_when_weight_is_zero() -> None:
    graph, high_risk, low_risk = _build_diamond_graph()
    start = graph.nearest_node(LonLat(lon=_A[0], lat=_A[1]))
    goal = graph.nearest_node(LonLat(lon=_D[0], lat=_D[1]))
    assert start is not None and goal is not None

    precinct_risk = {high_risk: 0.9, low_risk: 0.1}
    hops = graph.shortest_path(start, goal, mode="walking", precinct_risk=precinct_risk, risk_weight=0.0)

    assert hops is not None
    # A-B-D (~480m) is shorter than A-C-D (~570m), so a zero risk weight
    # should prefer it despite it being the high-risk precinct.
    assert all(hop.precinct_id == high_risk for hop in hops)


def test_shortest_path_reroutes_through_lower_risk_precinct_when_weighted() -> None:
    graph, high_risk, low_risk = _build_diamond_graph()
    start = graph.nearest_node(LonLat(lon=_A[0], lat=_A[1]))
    goal = graph.nearest_node(LonLat(lon=_D[0], lat=_D[1]))
    assert start is not None and goal is not None

    precinct_risk = {high_risk: 0.9, low_risk: 0.1}
    hops = graph.shortest_path(start, goal, mode="walking", precinct_risk=precinct_risk, risk_weight=10.0)

    assert hops is not None
    assert all(hop.precinct_id == low_risk for hop in hops)


def test_shortest_path_returns_none_for_disconnected_mode() -> None:
    graph, _high_risk, _low_risk = _build_diamond_graph()
    start = graph.nearest_node(LonLat(lon=_A[0], lat=_A[1]))
    goal = graph.nearest_node(LonLat(lon=_D[0], lat=_D[1]))
    assert start is not None and goal is not None

    hops = graph.shortest_path(start, goal, mode="rail", precinct_risk={}, risk_weight=0.0)
    assert hops is None


def test_nearest_node_snaps_to_closest_endpoint() -> None:
    graph, _high_risk, _low_risk = _build_diamond_graph()
    near_a = graph.nearest_node(LonLat(lon=_A[0] + 0.0001, lat=_A[1]))
    assert near_a is not None
    assert graph.node_point(near_a).lon == _A[0]
    assert graph.node_point(near_a).lat == _A[1]
