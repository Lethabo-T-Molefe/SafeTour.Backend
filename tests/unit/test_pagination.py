"""Unit tests for pagination helpers."""

from safetour.shared.utils.pagination import clamp_pagination


def test_clamp_pagination_bounds() -> None:
    assert clamp_pagination(-5, 500, max_limit=100) == (0, 100)
    assert clamp_pagination(10, 0, max_limit=100) == (10, 1)
    assert clamp_pagination(2, 25, max_limit=100) == (2, 25)
