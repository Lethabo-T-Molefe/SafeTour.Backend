"""FastAPI DI wiring for auth: the service factory, and the bearer-token
dependency every other module uses to identify the caller (explicit public
export — the one cross-module import the architecture allows outright)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from safetour.modules.auth.models import (
    SqlAlchemyAuthAccountRepository,
    SqlAlchemyRefreshTokenRepository,
)
from safetour.modules.auth.service import AuthService
from safetour.shared.dependencies import DbSession
from safetour.shared.security import decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_service(db: DbSession) -> AuthService:
    return AuthService(
        accounts=SqlAlchemyAuthAccountRepository(db),
        refresh_tokens=SqlAlchemyRefreshTokenRepository(db),
    )


async def get_current_account_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> UUID:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        payload = decode_access_token(credentials.credentials)
        return UUID(str(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc


CurrentAccountId = Annotated[UUID, Depends(get_current_account_id)]


async def require_admin(
    account_id: CurrentAccountId,
    db: DbSession,
) -> UUID:
    from safetour.modules.auth.models import AuthAccountModel

    row = await db.get(AuthAccountModel, account_id)
    if row is None or not row.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return account_id


CurrentAdminId = Annotated[UUID, Depends(require_admin)]
