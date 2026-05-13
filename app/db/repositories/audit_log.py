"""
AuditLog repository — append-only HIPAA compliance log.

Provides structured logging helpers for every domain event.
This repository intentionally DISABLES update and delete operations
— audit logs are immutable by design.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.audit_log import AuditLog
from app.models.enums import ActorType, AuditAction, AuditEntityType

logger = structlog.get_logger(__name__)


class AuditLogRepository(BaseRepository[AuditLog]):
    """
    Append-only repository for HIPAA-compliant audit logs.

    update() and soft_delete() raise NotImplementedError to enforce immutability.
    Use log_event() as the primary interface.
    """

    model = AuditLog

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ----------------------------------------------------------
    # Block mutation operations
    # ----------------------------------------------------------

    async def update(self, record_id: str, **kwargs: Any) -> AuditLog:  # type: ignore[override]
        raise NotImplementedError("AuditLog records are immutable and cannot be updated")

    async def soft_delete(self, record_id: str) -> bool:  # type: ignore[override]
        raise NotImplementedError("AuditLog records cannot be deleted")

    async def hard_delete(self, record_id: str, **kwargs) -> bool:  # type: ignore[override]
        raise NotImplementedError("AuditLog records cannot be deleted")

    # ----------------------------------------------------------
    # Primary write interface
    # ----------------------------------------------------------

    async def log_event(
        self,
        action: AuditAction,
        entity_type: AuditEntityType,
        entity_id: str | None = None,
        actor_type: ActorType = ActorType.SYSTEM,
        actor_id: str | None = None,
        actor_name: str | None = None,
        actor_role: str | None = None,
        description: str | None = None,
        previous_state: dict[str, Any] | None = None,
        new_state: dict[str, Any] | None = None,
        changed_fields: list[str] | None = None,
        case_id: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        ip_address: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """
        Append a single audit log entry.

        This is the primary API for all audit logging across the platform.
        Call this from services whenever state changes occur.
        """
        return await self.create(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_name=actor_name,
            actor_role=actor_role,
            description=description,
            previous_state=previous_state,
            new_state=new_state,
            changed_fields=changed_fields,
            case_id=case_id,
            request_id=request_id,
            trace_id=trace_id,
            ip_address=ip_address,
            metadata_=metadata,
        )

    # ----------------------------------------------------------
    # Query interface
    # ----------------------------------------------------------

    async def get_for_entity(
        self,
        entity_type: AuditEntityType,
        entity_id: str,
        limit: int = 100,
    ) -> list[AuditLog]:
        """Return all audit events for a specific entity, newest first."""
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_for_case(self, case_id: str, limit: int = 200) -> list[AuditLog]:
        """Return all audit events associated with a PA case, newest first."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.case_id == case_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_for_actor(
        self,
        actor_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AuditLog]:
        """Return audit events performed by a specific actor."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.actor_id == actor_id)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
