"""
SQLAlchemy declarative base and shared abstract model mixin.

All ORM models inherit from Base (DeclarativeBase).
Models with standard audit fields inherit from TimestampedModel.

Design:
- UUID primary keys prevent enumeration attacks and allow distributed ID generation
- created_at / updated_at auto-managed by SQLAlchemy event hooks
- deleted_at enables soft deletes — records are never physically removed
- __tablename__ auto-derived from class name (snake_case) if not overridden
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, String, event, func
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedColumn, mapped_column


class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base for all ORM models.

    All models in app/models/ must inherit from this class.
    """

    # Allows models to be converted to dicts easily
    def to_dict(self) -> dict[str, Any]:
        """Return model as a plain dict (column name → value)."""
        return {
            col.name: getattr(self, col.name)
            for col in self.__table__.columns
        }


class UUIDMixin:
    """
    UUID primary key mixin.

    Uses CHAR(36) in MySQL (UUID stored as string) for readability and portability.
    Alternatively use BINARY(16) for 50% storage savings in very large tables.
    """

    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID primary key",
    )


class TimestampMixin:
    """
    Automatic created_at / updated_at timestamp columns.

    created_at: set once on INSERT, never updated
    updated_at: updated automatically on every UPDATE via SQLAlchemy event
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="Record creation timestamp (UTC)",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        comment="Record last-updated timestamp (UTC)",
    )


class SoftDeleteMixin:
    """
    Soft delete support.

    Records are NEVER physically deleted — deleted_at is set instead.
    Repositories must filter WHERE deleted_at IS NULL.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
        comment="Soft delete timestamp — NULL means record is active",
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark this record as deleted without removing it from the database."""
        self.deleted_at = datetime.now(UTC)


class AuditMixin:
    """
    Audit trail columns for compliance.

    Records who created and last modified each record.
    user IDs reference the users table (not enforced as FK to allow service accounts).
    """

    created_by: Mapped[str | None] = mapped_column(
        CHAR(36),
        nullable=True,
        comment="UUID of user who created this record",
    )
    updated_by: Mapped[str | None] = mapped_column(
        CHAR(36),
        nullable=True,
        comment="UUID of user who last updated this record",
    )


class BaseModel(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """
    Full-featured abstract base model.

    Combines UUID primary key, timestamps, and soft deletes.
    Use as the base for all domain models:

        class PACase(BaseModel):
            __tablename__ = "pa_cases"
            ...
    """

    __abstract__ = True
