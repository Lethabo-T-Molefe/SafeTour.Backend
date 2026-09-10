from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from safetour.modules.emergency.domain import (
    ShareWindowTooLongError,
    TripForbiddenError,
    TripNotFoundError,
)


def register_emergency_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(TripNotFoundError)
    async def _not_found(_: Request, exc: TripNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(TripForbiddenError)
    async def _forbidden(_: Request, exc: TripForbiddenError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(ShareWindowTooLongError)
    async def _bad_request(_: Request, exc: ShareWindowTooLongError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})
