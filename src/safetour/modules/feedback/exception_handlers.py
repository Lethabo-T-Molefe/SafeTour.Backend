from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from safetour.modules.feedback.domain import FeedbackContentRejectedError, FeedbackRateLimitedError


def register_feedback_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(FeedbackRateLimitedError)
    async def _rate_limited(_: Request, exc: FeedbackRateLimitedError) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    @app.exception_handler(FeedbackContentRejectedError)
    async def _rejected(_: Request, exc: FeedbackContentRejectedError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})
