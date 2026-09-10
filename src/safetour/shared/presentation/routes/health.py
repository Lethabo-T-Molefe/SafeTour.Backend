"""
Health and readiness routes.

``/health`` is a liveness probe that never touches the database. ``/ready``
additionally pings PostgreSQL, matching NFR-REL-1's "core routing and risk
keep working ... when optional services are down" by failing loudly only when
the hard dependency (the database) is actually unreachable.
"""

from fastapi import APIRouter
from sqlalchemy import text

from safetour.shared.dependencies import DbSession

router = APIRouter()


@router.get("/health")
async def api_health() -> dict[str, str]:
    return {"status": "healthy", "layer": "api/v1"}


@router.get("/ready")
async def api_ready(db: DbSession) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"status": "ready"}
