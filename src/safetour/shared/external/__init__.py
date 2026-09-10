"""Shared external clients."""

from safetour.shared.external.http_client import ExternalApiClient
from safetour.shared.external.power_status_client import PowerStatusClient
from safetour.shared.external.weather_client import WeatherClient

__all__ = ["ExternalApiClient", "PowerStatusClient", "WeatherClient"]
