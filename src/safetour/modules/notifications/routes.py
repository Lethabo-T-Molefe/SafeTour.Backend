"""Notifications API routes (FR-NOT-2)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from safetour.modules.auth.dependencies import CurrentAccountId
from safetour.modules.notifications.dependencies import get_notifications_port
from safetour.modules.notifications.schemas import (
    AlertPreferenceResponse,
    AlertPreferenceUpdateRequest,
    SubscribeRequest,
)
from safetour.modules.notifications.service import NotificationsService

router = APIRouter(prefix="/notifications", tags=["notifications"])

NotificationsServiceDep = Annotated[NotificationsService, Depends(get_notifications_port)]


@router.post("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def subscribe(account_id: CurrentAccountId, body: SubscribeRequest, service: NotificationsServiceDep) -> None:
    await service.subscribe(account_id, body.endpoint, body.keys)


@router.get("/preferences", response_model=AlertPreferenceResponse)
async def get_preferences(account_id: CurrentAccountId, service: NotificationsServiceDep) -> AlertPreferenceResponse:
    preference = await service.get_preferences(account_id)
    return AlertPreferenceResponse.model_validate(preference, from_attributes=True)


@router.put("/preferences", response_model=AlertPreferenceResponse)
async def update_preferences(
    account_id: CurrentAccountId, body: AlertPreferenceUpdateRequest, service: NotificationsServiceDep
) -> AlertPreferenceResponse:
    preference = await service.update_preferences(account_id, body.non_safety_opt_in)
    return AlertPreferenceResponse.model_validate(preference, from_attributes=True)
