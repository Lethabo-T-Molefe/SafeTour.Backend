"""
Application settings
====================
Loaded once at import time from environment variables and an optional ``.env``.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed configuration for the SafeTour AI Sentinel API."""

    PROJECT_NAME: str = "SafeTour AI Sentinel"
    DEBUG: bool = True
    VERSION: str = "0.1.0"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/safetour"
    # Prefer Alembic in shared/prod environments; useful for local bootstrapping only.
    AUTO_CREATE_TABLES: bool = False

    # Auth (FR-AUTH-2, NFR-SEC-2): short-lived access token, longer-lived rotating
    # refresh token, and a lockout window after repeated failed logins.
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15

    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # CFR-10 / FR-LOC-1: officially supported interface and assistant languages.
    SUPPORTED_LANGUAGES: list[str] = ["en", "af", "zu", "xh", "st", "tn"]
    DEFAULT_LANGUAGE: str = "en"

    # Pilot area for the documented prototype (student is TUT, Tshwane).
    PILOT_AREA_NAME: str = "Tshwane"

    # Risk scoring / routing thresholds (naive pre-model placeholders — see
    # modules/risk/service.py; superseded once MLR-1..MLR-5 land a promoted model).
    RISK_BAND_LOW_MAX: float = 0.33
    RISK_BAND_MEDIUM_MAX: float = 0.66

    # Community reports (FR-REP-3 / MLR-7): confidence decays to ~0 by this many
    # days unless re-confirmed, and never influences risk beyond this cap while
    # still only "pending".
    REPORT_DECAY_HALF_LIFE_DAYS: float = 14.0
    REPORT_UNVERIFIED_MAX_WEIGHT: float = 0.15

    # Emergency (NFR-PRIV-2 / NFR-PRIV-4): live trip-share and check-in data is
    # transient by design and expires with the trip.
    TRIP_SHARE_MAX_HOURS: int = 12

    # Optional integrations (all "request time, optional" per section 28 — the
    # app must run with none of these configured, degrading deterministically).
    LLM_API_KEY: str | None = None
    LLM_MODEL: str = "claude-haiku-4-5-20251001"
    WEATHER_API_URL: str | None = None
    POWER_STATUS_API_URL: str | None = None
    PUSH_VAPID_PUBLIC_KEY: str | None = None
    PUSH_VAPID_PRIVATE_KEY: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
