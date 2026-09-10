from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from safetour.modules.itineraries.domain import ItineraryForbiddenError, ItineraryNotFoundError


def register_itineraries_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ItineraryNotFoundError)
    async def _not_found(_: Request, exc: ItineraryNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ItineraryForbiddenError)
    async def _forbidden(_: Request, exc: ItineraryForbiddenError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})
