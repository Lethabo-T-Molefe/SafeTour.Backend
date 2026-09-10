from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from safetour.modules.reports.domain import ReportNotFoundError, ReportRateLimitedError


def register_reports_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ReportNotFoundError)
    async def _not_found(_: Request, exc: ReportNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ReportRateLimitedError)
    async def _rate_limited(_: Request, exc: ReportRateLimitedError) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)})
