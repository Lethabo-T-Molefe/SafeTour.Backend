"""
Async SQLAlchemy engine / session factory
=========================================
Shared infrastructure: nearly every persistence adapter needs it.
Session lifetime is request-scoped via ``get_db`` + FastAPI Depends.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from safetour.shared.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,  # drop stale connections before checkout
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # allow using attributes after commit
    autoflush=False,
)


class Base(DeclarativeBase):
    """Declarative base — all ORM models subclass this."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a DB session and commit on success / rollback on error.

    Used as ``Depends(get_db)``. Repositories should ``flush`` when they need
    generated IDs; the final ``commit`` happens here at request end.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
