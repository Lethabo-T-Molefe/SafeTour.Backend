"""Auth API routes: register, login, refresh, logout."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from safetour.modules.auth.dependencies import CurrentAccountId, get_auth_service
from safetour.modules.auth.schemas import (
    AuthAccountResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from safetour.modules.auth.service import AuthService, LoginInput, RegisterInput

router = APIRouter(prefix="/auth", tags=["auth"])

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/register", response_model=AuthAccountResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, service: AuthServiceDep) -> AuthAccountResponse:
    account = await service.register(
        RegisterInput(email=str(body.email), password=body.password, consent=body.consent)
    )
    return AuthAccountResponse.model_validate(account, from_attributes=True)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    _account, tokens = await service.login(LoginInput(email=str(body.email), password=body.password))
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, service: AuthServiceDep) -> TokenResponse:
    tokens = await service.refresh(body.refresh_token)
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(account_id: CurrentAccountId, service: AuthServiceDep) -> None:
    await service.logout(account_id)
