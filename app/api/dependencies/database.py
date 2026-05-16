"""
Async database session dependency.

Provides a transactional AsyncSession per-request. Commits on success,
rolls back on any exception, ensuring request atomicity.
"""

from __future__ import annotations

from typing import Annotated, AsyncGenerator

import structlog
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session.database import get_session_factory

logger = structlog.get_logger(__name__)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a scoped async database session.

    - Commits automatically on success
    - Rolls back automatically on exception
    - Session is closed when the request completes
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


DbSession = Annotated[AsyncSession, Depends(get_db_session)]
