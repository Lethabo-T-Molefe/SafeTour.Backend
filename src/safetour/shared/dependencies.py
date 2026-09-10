"""
Shared FastAPI dependency helpers
=================================
Request-scoped DB session alias used by module composition roots.
Module-specific wiring (e.g. user repositories) lives in each module.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from safetour.shared.database import get_db

# Re-export a typed alias used by module dependencies / routers.
DbSession = Annotated[AsyncSession, Depends(get_db)]
