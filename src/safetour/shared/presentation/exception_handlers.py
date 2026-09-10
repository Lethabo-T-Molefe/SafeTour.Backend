"""
Map shared application exceptions to HTTP responses.

Module-specific domain handlers are registered by each module (see users).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from safetour.shared.exceptions import AppError, ForbiddenError, UnauthorizedError


def register_exception_handlers(app: FastAPI) -> None:
    """Attach cross-cutting exception handlers to ``app`` (call once at startup)."""

    @app.exception_handler(UnauthorizedError)
    async def unauthorized_handler(_: Request, exc: UnauthorizedError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": exc.message})

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(_: Request, exc: ForbiddenError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": exc.message})

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": exc.message})
