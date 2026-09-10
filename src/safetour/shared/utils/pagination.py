"""Pagination helpers shared across layers that need safe page bounds."""


def clamp_pagination(offset: int, limit: int, *, max_limit: int = 100) -> tuple[int, int]:
    """
    Normalize pagination arguments.

    Parameters
    ----------
    offset:
        Requested skip count (negative values become 0).
    limit:
        Requested page size, clamped to ``[1, max_limit]``.
    max_limit:
        Upper bound to protect the database from huge page requests.
    """
    safe_offset = max(0, offset)
    safe_limit = max(1, min(limit, max_limit))
    return safe_offset, safe_limit
