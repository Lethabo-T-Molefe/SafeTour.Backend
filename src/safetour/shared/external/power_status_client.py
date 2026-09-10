"""
Optional power-status signal feeding FR-POW-1 (contextual risk during a
confirmed outage or load reduction). Request-time, optional, omit on failure.

With no ``POWER_STATUS_API_URL`` configured, callers fall back to the
``PowerStatus`` rows an administrator maintains manually via the admin module.
"""

from __future__ import annotations

from safetour.shared.config import settings
from safetour.shared.external.http_client import ExternalApiClient


class PowerStatusClient:
    def __init__(self) -> None:
        self._client = (
            ExternalApiClient(settings.POWER_STATUS_API_URL)
            if settings.POWER_STATUS_API_URL
            else None
        )

    async def is_area_affected(self, precinct_id: str) -> bool | None:
        if self._client is None:
            return None
        data = await self._client.get_json(f"/status/{precinct_id}")
        if not data:
            return None
        return bool(data.get("outage_active", False))
