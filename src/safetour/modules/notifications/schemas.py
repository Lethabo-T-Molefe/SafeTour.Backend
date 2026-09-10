from __future__ import annotations

from pydantic import BaseModel


class SubscribeRequest(BaseModel):
    endpoint: str
    keys: dict[str, str]


class AlertPreferenceResponse(BaseModel):
    safety_alerts_opt_in: bool
    non_safety_opt_in: bool


class AlertPreferenceUpdateRequest(BaseModel):
    non_safety_opt_in: bool
