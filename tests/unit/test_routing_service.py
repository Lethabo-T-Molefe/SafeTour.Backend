"""Unit tests for routing math helpers (FR-ROUTE-2: respects distance/time limits)."""

from safetour.modules.routing.domain import LonLat, speed_kmh_for_mode
from safetour.modules.routing.graph import haversine_m


def test_haversine_distance_cape_town_to_johannesburg_is_roughly_correct() -> None:
    cape_town = LonLat(lon=18.4241, lat=-33.9249)
    johannesburg = LonLat(lon=28.0473, lat=-26.2041)
    distance_km = haversine_m(cape_town, johannesburg) / 1000
    # Great-circle distance is ~1270km; allow a generous tolerance.
    assert 1200 < distance_km < 1350


def test_speed_falls_back_to_walking_for_unknown_mode() -> None:
    assert speed_kmh_for_mode("unknown_mode") == speed_kmh_for_mode("walking")
    assert speed_kmh_for_mode("rail") > speed_kmh_for_mode("walking")
