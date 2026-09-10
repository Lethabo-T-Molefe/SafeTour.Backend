"""
Optional weather signal (section 28: request-time, optional, omit on failure).

Not a risk driver on its own — surfaced as a contextual hint only (e.g. heavy
rain lowers pedestrian visibility / raises exposure at night stops).
"""

from __future__ import annotations

from safetour.shared.config import settings
from safetour.shared.external.http_client import ExternalApiClient


class WeatherClient:
    def __init__(self) -> None:
        self._client = (
            ExternalApiClient(settings.WEATHER_API_URL) if settings.WEATHER_API_URL else None
        )

    async def get_condition(self, lat: float, lon: float) -> str | None:
        if self._client is None:
            return None
        data = await self._client.get_json("/current", params={"lat": lat, "lon": lon})
        if not data:
            return None
        condition = data.get("condition")
        return str(condition) if condition else None
