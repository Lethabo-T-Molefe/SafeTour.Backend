from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from safetour.modules import (
    admin,
    assistant,
    auth,
    emergency,
    feedback,
    geo,
    itineraries,
    notifications,
    reports,
    risk,
    routing,
    users,
)

# Import every module's ORM models so Base.metadata is fully populated for
# Alembic autogenerate and for AUTO_CREATE_TABLES local bootstrapping.
from safetour.modules.admin import models as _admin_models  # noqa: F401
from safetour.modules.auth import models as _auth_models  # noqa: F401
from safetour.modules.emergency import models as _emergency_models  # noqa: F401
from safetour.modules.feedback import models as _feedback_models  # noqa: F401
from safetour.modules.geo import models as _geo_models  # noqa: F401
from safetour.modules.itineraries import models as _itineraries_models  # noqa: F401
from safetour.modules.notifications import models as _notifications_models  # noqa: F401
from safetour.modules.reports import models as _reports_models  # noqa: F401
from safetour.modules.risk import models as _risk_models  # noqa: F401
from safetour.modules.users import models as _users_models  # noqa: F401
from safetour.shared.config import settings
from safetour.shared.database import Base, engine
from safetour.shared.presentation.exception_handlers import register_exception_handlers
from safetour.shared.presentation.routes.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Prefer Alembic migrations in shared environments. ``AUTO_CREATE_TABLES``
    is a local convenience flag only."""
    if settings.AUTO_CREATE_TABLES:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    print(f"{settings.PROJECT_NAME} v{settings.VERSION} started successfully!")
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
auth.register_auth_exception_handlers(app)
reports.register_reports_exception_handlers(app)
itineraries.register_itineraries_exception_handlers(app)
emergency.register_emergency_exception_handlers(app)
feedback.register_feedback_exception_handlers(app)
admin.register_admin_exception_handlers(app)

app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(geo.router, prefix="/api/v1")
app.include_router(risk.router, prefix="/api/v1")
app.include_router(routing.router, prefix="/api/v1")
app.include_router(itineraries.router, prefix="/api/v1")
app.include_router(assistant.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(emergency.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "status": "running",
        "version": settings.VERSION,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("safetour.main:app", host="0.0.0.0", port=8000, reload=True)
