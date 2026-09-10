from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from safetour.modules.auth.domain import (
    AccountLockedError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidEmailError,
    InvalidRefreshTokenError,
)


def register_auth_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(EmailAlreadyRegisteredError)
    async def _conflict(_: Request, exc: EmailAlreadyRegisteredError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(InvalidCredentialsError)
    async def _unauthorized(_: Request, exc: InvalidCredentialsError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(AccountLockedError)
    async def _locked(_: Request, exc: AccountLockedError) -> JSONResponse:
        return JSONResponse(status_code=423, content={"detail": str(exc), "locked_until": exc.locked_until.isoformat()})

    @app.exception_handler(InvalidRefreshTokenError)
    async def _invalid_refresh(_: Request, exc: InvalidRefreshTokenError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(InvalidEmailError)
    async def _invalid_email(_: Request, exc: InvalidEmailError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})
