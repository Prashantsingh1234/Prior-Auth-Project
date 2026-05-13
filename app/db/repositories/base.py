"""
Generic async base repository.

Provides type-safe, async CRUD operations for all domain models.
All domain repositories inherit from BaseRepository[T].

Design:
- Generic[ModelT] — full type inference in subclasses and callers
- Soft delete by default — hard_delete() available but requires explicit call
- All queries filter deleted_at IS NULL by default (include_deleted=True to override)
- Structured logging on every operation for auditability
- SQLAlchemy exceptions caught and re-raised as PABaseException subtypes
- Retry on transient DB errors via tenacity

Usage:
    class PAcaseRepository(BaseRepository[PACase]):
        model = PACase

        async def find_by_status(self, status: CaseStatus) -> list[PACase]:
            stmt = (
                select(self.model)
                .where(self.model.status == status, self.model.deleted_at.is_(None))
                .order_by(self.model.created_at.desc())
            )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

import structlog
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.exceptions.base import DatabaseError, ResourceNotFoundError
from app.db.base.model import BaseModel

logger = structlog.get_logger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)

# Retry on transient DB errors (connection drops, deadlocks)
_DB_RETRY_ERRORS = (OperationalError,)


class BaseRepository(Generic[ModelT]):
    """
    Generic async repository providing standard CRUD operations.

    Type parameter ModelT must be a subclass of BaseModel
    (which has id, created_at, updated_at, deleted_at).

    Subclasses declare `model: type[ModelT]` as a class variable.
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._log = structlog.get_logger(
            self.__class__.__name__,
            model=self.model.__tablename__,
        )

    # ----------------------------------------------------------
    # Read Operations
    # ----------------------------------------------------------

    @retry(
        retry=retry_if_exception_type(_DB_RETRY_ERRORS),
        wait=wait_exponential(multiplier=0.1, min=0.1, max=2.0),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def get_by_id(
        self,
        record_id: str,
        include_deleted: bool = False,
    ) -> ModelT | None:
        """
        Fetch a single record by its UUID primary key.

        Returns None if not found (or soft-deleted and include_deleted=False).
        """
        try:
            stmt = select(self.model).where(self.model.id == record_id)
            if not include_deleted:
                stmt = stmt.where(self.model.deleted_at.is_(None))
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            self._log.error("repository.get_by_id.failed", record_id=record_id, error=str(exc))
            raise DatabaseError(details={"record_id": record_id}) from exc

    async def get_by_id_or_raise(
        self,
        record_id: str,
        not_found_exception: type[ResourceNotFoundError] = ResourceNotFoundError,
    ) -> ModelT:
        """
        Fetch a record by ID or raise ResourceNotFoundError (or subclass).

        Use this in route handlers where a missing record is a client error.
        """
        record = await self.get_by_id(record_id)
        if record is None:
            raise not_found_exception(
                details={"id": record_id, "model": self.model.__tablename__}
            )
        return record

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 50,
        include_deleted: bool = False,
        order_by_created: bool = True,
    ) -> list[ModelT]:
        """
        Fetch a paginated list of records.

        Args:
            skip:             Rows to skip (offset)
            limit:            Max rows to return (capped at 500 for safety)
            include_deleted:  Include soft-deleted records
            order_by_created: Order newest first
        """
        safe_limit = min(limit, 500)
        try:
            stmt = select(self.model)
            if not include_deleted:
                stmt = stmt.where(self.model.deleted_at.is_(None))
            if order_by_created:
                stmt = stmt.order_by(self.model.created_at.desc())
            stmt = stmt.offset(skip).limit(safe_limit)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            self._log.error("repository.get_all.failed", error=str(exc))
            raise DatabaseError() from exc

    async def count(self, include_deleted: bool = False) -> int:
        """Return the total count of records in this table."""
        try:
            stmt = select(func.count()).select_from(self.model)
            if not include_deleted:
                stmt = stmt.where(self.model.deleted_at.is_(None))
            result = await self.session.execute(stmt)
            return result.scalar_one()
        except SQLAlchemyError as exc:
            raise DatabaseError() from exc

    async def exists(self, record_id: str) -> bool:
        """Return True if a non-deleted record with this ID exists."""
        try:
            stmt = (
                select(func.count())
                .select_from(self.model)
                .where(
                    self.model.id == record_id,
                    self.model.deleted_at.is_(None),
                )
            )
            result = await self.session.execute(stmt)
            return result.scalar_one() > 0
        except SQLAlchemyError as exc:
            raise DatabaseError(details={"record_id": record_id}) from exc

    # ----------------------------------------------------------
    # Write Operations
    # ----------------------------------------------------------

    async def create(self, **kwargs: Any) -> ModelT:
        """
        Create and persist a new record.

        Args:
            **kwargs: Column values passed to the model constructor

        Returns:
            The persisted model instance with DB-generated fields populated
        """
        try:
            instance = self.model(**kwargs)
            self.session.add(instance)
            await self.session.flush()  # Get DB-generated defaults (id, timestamps)
            await self.session.refresh(instance)
            self._log.info(
                "repository.created",
                record_id=instance.id,
            )
            return instance
        except IntegrityError as exc:
            await self.session.rollback()
            self._log.warning(
                "repository.create.integrity_error",
                error=str(exc.orig),
                kwargs_keys=list(kwargs.keys()),
            )
            from app.core.exceptions.base import ResourceConflictError
            raise ResourceConflictError(
                details={"constraint": str(exc.orig)}
            ) from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            self._log.error("repository.create.failed", error=str(exc))
            raise DatabaseError() from exc

    async def update(self, record_id: str, **kwargs: Any) -> ModelT:
        """
        Update specific fields on an existing record.

        Args:
            record_id: UUID of the record to update
            **kwargs:  Fields to update (only provided fields are changed)

        Returns:
            Updated model instance

        Raises:
            ResourceNotFoundError: If the record does not exist
        """
        instance = await self.get_by_id_or_raise(record_id)
        try:
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            instance.updated_at = datetime.now(UTC)
            await self.session.flush()
            await self.session.refresh(instance)
            self._log.info(
                "repository.updated",
                record_id=record_id,
                updated_fields=list(kwargs.keys()),
            )
            return instance
        except SQLAlchemyError as exc:
            await self.session.rollback()
            self._log.error(
                "repository.update.failed",
                record_id=record_id,
                error=str(exc),
            )
            raise DatabaseError(details={"record_id": record_id}) from exc

    async def soft_delete(self, record_id: str) -> bool:
        """
        Soft-delete a record by setting deleted_at to now.

        Returns:
            True if the record was found and soft-deleted
            False if the record did not exist or was already deleted
        """
        instance = await self.get_by_id(record_id)
        if instance is None:
            return False
        try:
            instance.soft_delete()
            await self.session.flush()
            self._log.info("repository.soft_deleted", record_id=record_id)
            return True
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise DatabaseError(details={"record_id": record_id}) from exc

    async def hard_delete(self, record_id: str, include_deleted: bool = True) -> bool:
        """
        Permanently delete a record from the database.

        Use sparingly — prefer soft_delete() for audit compliance.
        Returns True if the record was found and deleted.
        """
        instance = await self.get_by_id(record_id, include_deleted=include_deleted)
        if instance is None:
            return False
        try:
            await self.session.delete(instance)
            await self.session.flush()
            self._log.warning(
                "repository.hard_deleted",
                record_id=record_id,
                model=self.model.__tablename__,
            )
            return True
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise DatabaseError(details={"record_id": record_id}) from exc

    # ----------------------------------------------------------
    # Batch Operations
    # ----------------------------------------------------------

    async def bulk_create(self, items: list[dict[str, Any]]) -> list[ModelT]:
        """
        Create multiple records in a single transaction.

        Args:
            items: List of dicts, each containing fields for one record

        Returns:
            List of created model instances
        """
        if not items:
            return []
        try:
            instances = [self.model(**item) for item in items]
            self.session.add_all(instances)
            await self.session.flush()
            for instance in instances:
                await self.session.refresh(instance)
            self._log.info("repository.bulk_created", count=len(instances))
            return instances
        except IntegrityError as exc:
            await self.session.rollback()
            from app.core.exceptions.base import ResourceConflictError
            raise ResourceConflictError(details={"error": str(exc.orig)}) from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise DatabaseError() from exc

    # ----------------------------------------------------------
    # Internal query builder helper
    # ----------------------------------------------------------

    def _base_query(self, include_deleted: bool = False) -> Select:
        """Return a base SELECT query with optional soft-delete filter."""
        stmt = select(self.model)
        if not include_deleted:
            stmt = stmt.where(self.model.deleted_at.is_(None))
        return stmt
