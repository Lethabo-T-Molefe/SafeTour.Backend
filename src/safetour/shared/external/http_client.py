"""
Base async HTTP client for optional third-party integrations.

Every concrete client built on this (weather, power status, push) is an
optional, request-time integration per the integrations table: a timeout or
error must degrade to "omit the signal", never fail the request it feeds.
"""

from __future__ import annotations

from typing import Any

import httpx


class ExternalApiClient:
    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}/{path.lstrip('/')}", params=params)
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                return data
        except (httpx.HTTPError, ValueError):
            return None
