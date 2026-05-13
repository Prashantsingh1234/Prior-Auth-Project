"""
Alembic migration environment.

Configures the async engine for online migrations and loads
the target metadata from all ORM models.

Run migrations:
    alembic upgrade head
    alembic downgrade -1
    alembic revision --autogenerate -m "add pa_cases table"
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import Base and all models so Alembic sees the metadata
from app.db.base.model import Base
from app.core.config.settings import get_settings

# Alembic Config object (provides access to alembic.ini values)
config = context.config

# Configure Python logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the migration target metadata
target_metadata = Base.metadata


def get_database_url() -> str:
    """Load the DB URL from application settings (not alembic.ini)."""
    settings = get_settings()
    return settings.database_url


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode (generate SQL scripts without a live DB).
    Useful for generating migration scripts to review before applying.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations against a live database."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # No pooling for migration runs
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (against a live database)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
