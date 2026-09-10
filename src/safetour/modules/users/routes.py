"""Profile API routes: GET/PUT /users/me, /users/me/preferences, export & delete."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from safetour.modules.auth.dependencies import CurrentAccountId, get_auth_service
from safetour.modules.auth.service import AuthService
from safetour.modules.users.dependencies import get_profile_service
from safetour.modules.users.schemas import (
    ExportedDataResponse,
    ProfileResponse,
    ProfileUpdateRequest,
)
from safetour.modules.users.service import ProfileService, UpdateProfileInput

router = APIRouter(prefix="/users", tags=["users"])

ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.get("/me", response_model=ProfileResponse)
async def get_me(account_id: CurrentAccountId, service: ProfileServiceDep) -> ProfileResponse:
    profile = await service.get_or_create(account_id)
    return ProfileResponse.model_validate(profile, from_attributes=True)


@router.put("/me/preferences", response_model=ProfileResponse)
async def update_preferences(
    account_id: CurrentAccountId,
    body: ProfileUpdateRequest,
    service: ProfileServiceDep,
) -> ProfileResponse:
    profile = await service.update(account_id, UpdateProfileInput(**body.model_dump(exclude_unset=True)))
    return ProfileResponse.model_validate(profile, from_attributes=True)


@router.get("/me/export", response_model=ExportedDataResponse)
async def export_me(account_id: CurrentAccountId, service: ProfileServiceDep) -> ExportedDataResponse:
    data = await service.export(account_id)
    return ExportedDataResponse(profile=data.profile)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    account_id: CurrentAccountId,
    profiles: ProfileServiceDep,
    auth: AuthServiceDep,
) -> None:
    await profiles.delete(account_id)
    await auth.delete_account(account_id)
