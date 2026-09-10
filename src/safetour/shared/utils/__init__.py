"""Pure helpers shared across modules."""

from safetour.shared.utils.datetime import utc_now
from safetour.shared.utils.pagination import clamp_pagination

__all__ = ["clamp_pagination", "utc_now"]
