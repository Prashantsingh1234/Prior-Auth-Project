"""
Async SQLAlchemy engine and session management.

Design:
- Single async engine instance created at startup (init_db_connection)
- async_sessionmaker factory creates a new session per request
- get_db() is a FastAPI dependency that yields a session and auto-commits/rolls-back
- Connection pool settings come from Settings for environment-specific tuning
- get_db_health() is used by the health check endpoint

Usage in routes:
    @router.get("/cases")
    async def list_cases(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(PACase))
        ...
"""

from __future__ import annotations

import structlog
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql import text

from app.core.config.settings import get_settings

logger = structlog.get_logger(__name__)

# Module-level singletons — initialized in init_db_connection()
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db_connection() -> None:
    """
    Create the async SQLAlchemy engine and session factory.

    Called once during application startup lifespan.
    """
    global _engine, _session_factory

    settings = get_settings()

    _engine = create_async_engine(
        settings.database_url,
        # Pool configuration
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        # Recycle connections to avoid stale connection errors
        pool_recycle=settings.db_pool_recycle,
        # Pre-ping tests connection before handing it out from pool
        pool_pre_ping=True,
        # SQL query logging — always False in production to prevent data leakage
        echo=settings.db_echo,
        # Use the JSON serializer for JSON columns
        json_serializer=lambda obj: __import__("orjson").dumps(obj).decode(),
        json_deserializer=lambda s: __import__("orjson").loads(s),
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        # Don't expire objects on commit — prevents lazy-load errors on detached instances
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Validate connectivity at startup
    try:
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info(
            "database.connection_pool_initialized",
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            host=settings.db_host,
            db=settings.db_name,
        )
    except OperationalError as exc:
        logger.error(
            "database.connection_failed",
            error=str(exc),
            host=settings.db_host,
        )
        raise


async def close_db_connection() -> None:
    """
    Dispose the async engine and close all pool connections.

    Called during application shutdown lifespan.
    """
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("database.connection_pool_closed")


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory — raises if not yet initialized."""
    if _session_factory is None:
        raise RuntimeError("Database session factory not initialized. Call init_db_connection() first.")
    return _session_factory


async def get_db() -> AsyncSession:  # type: ignore[return]
    """
    FastAPI dependency that yields a database session.

    Handles commit on success and rollback on exception automatically.
    Use as:
        async with get_db() as db: ...
    OR inject via Depends(get_db).
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_health() -> bool:
    """
    Lightweight connectivity check for the health endpoint.

    Returns True if the database is reachable, False otherwise.
    Does NOT raise — the health check handles failures gracefully.
    """
    if _engine is None:
        return False
    try:
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
