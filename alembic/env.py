"""Alembic environment — async SQLAlchemy."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import every module's ORM models so Base.metadata is populated for autogenerate.
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
from safetour.shared.database import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
