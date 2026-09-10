from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from safetour.modules.admin.domain import InvalidIngestRowError
from safetour.modules.risk.domain import PromotionBlockedError


def register_admin_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PromotionBlockedError)
    async def _promotion_blocked(_: Request, exc: PromotionBlockedError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(InvalidIngestRowError)
    async def _invalid_row(_: Request, exc: InvalidIngestRowError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})
