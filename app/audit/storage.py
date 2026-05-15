"""
Compliance-ready audit storage backends.

Two backends, always used together:
  1. DatabaseAuditStorage  — primary, durable, queryable (MySQL via SQLAlchemy)
  2. StructlogAuditStorage — secondary, for log aggregation (ELK/CloudWatch/Datadog)

Both backends are async.  Both are fire-and-forget from the writer's perspective —
errors are caught, logged, and never re-raised to avoid killing the worker.

DatabaseAuditStorage writes to the `audit_logs` table in batches (up to 50 rows
per transaction, max 1-second wait).  Each row maps one AuditRecord to the
enhanced AuditLog ORM model.

StructlogAuditStorage emits a structured log entry per record using the
PII-masked log_data field.  Severity → log level mapping ensures ERROR records
appear in alerting pipelines.

Protocol (ABC):

    class AuditStorageBackend(ABC):
        async def write(self, record: AuditRecord) -> None: ...
        async def write_batch(self, records: list[AuditRecord]) -> None: ...
        async def close(self) -> None: ...
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import structlog

from app.audit.models import AuditCategory, AuditRecord, AuditSeverity

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class AuditStorageBackend(ABC):
    """Abstract base for all audit storage backends."""

    @abstractmethod
    async def write(self, record: AuditRecord) -> None:
        """Write a single audit record."""

    @abstractmethod
    async def write_batch(self, records: list[AuditRecord]) -> None:
        """Write a batch of audit records in one operation."""

    async def close(self) -> None:
        """Release any held resources (called on application shutdown)."""


# ---------------------------------------------------------------------------
# 1. Database backend
# ---------------------------------------------------------------------------

class DatabaseAuditStorage(AuditStorageBackend):
    """
    Writes audit records to the MySQL audit_logs table.

    Uses a fresh SQLAlchemy session per batch to avoid connection leaks.
    Inserts are append-only — no UPDATE or DELETE ever issued here.
    """

    def __init__(self, session_factory=None) -> None:
        self._session_factory = session_factory

    def _get_factory(self):
        if self._session_factory is not None:
            return self._session_factory
        from app.db.session.database import get_session_factory
        return get_session_factory()

    async def write(self, record: AuditRecord) -> None:
        await self.write_batch([record])

    async def write_batch(self, records: list[AuditRecord]) -> None:
        if not records:
            return
        factory = self._get_factory()
        if factory is None:
            logger.warning(
                "audit.db_storage.no_session_factory",
                count=len(records),
            )
            return

        t0 = time.monotonic()
        try:
            async with factory() as session:
                orm_rows = [self._to_orm(r) for r in records]
                session.add_all(orm_rows)
                await session.commit()
            elapsed = (time.monotonic() - t0) * 1000
            logger.debug(
                "audit.db_storage.batch_written",
                count=len(records),
                elapsed_ms=round(elapsed, 1),
            )
        except Exception as exc:
            logger.error(
                "audit.db_storage.write_failed",
                count=len(records),
                error=str(exc),
                exc_info=True,
            )
            # Attempt individual writes to salvage partial success
            await self._fallback_individual(records, factory)

    async def _fallback_individual(self, records: list[AuditRecord], factory) -> None:
        """Try to persist each record individually when a batch fails."""
        for record in records:
            try:
                async with factory() as session:
                    session.add(self._to_orm(record))
                    await session.commit()
            except Exception as exc:
                logger.error(
                    "audit.db_storage.individual_write_failed",
                    event_id=record.event_id,
                    category=record.category.value,
                    error=str(exc),
                )

    @staticmethod
    def _to_orm(record: AuditRecord):
        """Map an AuditRecord to the AuditLog ORM model."""
        from app.models.audit_log import AuditLog
        from app.models.enums import ActorType, AuditAction, AuditEntityType

        # Map AuditCategory → AuditAction (best-effort for existing enum)
        action_map = {
            AuditCategory.API_REQUEST:     AuditAction.READ,
            AuditCategory.OCR:             AuditAction.OCR_PROCESSED,
            AuditCategory.EXTRACTION:      AuditAction.AI_INFERENCE,
            AuditCategory.RETRIEVAL:       AuditAction.READ,
            AuditCategory.LLM_CALL:        AuditAction.AI_INFERENCE,
            AuditCategory.REVIEWER_ACTION: AuditAction.STATUS_CHANGE,
            AuditCategory.DECISION:        AuditAction.DECISION_MADE,
            AuditCategory.CLARIFICATION:   AuditAction.STATUS_CHANGE,
            AuditCategory.ERROR:           AuditAction.UPDATE,
        }
        actor_type_map = {
            "system":           ActorType.SYSTEM,
            "user":             ActorType.USER,
            "reviewer":         ActorType.USER,
            "ai":               ActorType.AI,
            "api_client":       ActorType.USER,
            "external_service": ActorType.SYSTEM,
        }
        entity_type_map = {
            AuditCategory.API_REQUEST:     AuditEntityType.SYSTEM,
            AuditCategory.OCR:             AuditEntityType.DOCUMENT,
            AuditCategory.EXTRACTION:      AuditEntityType.DOCUMENT,
            AuditCategory.RETRIEVAL:       AuditEntityType.POLICY_MATCH,
            AuditCategory.LLM_CALL:        AuditEntityType.EVALUATION,
            AuditCategory.REVIEWER_ACTION: AuditEntityType.REVIEWER_ACTION,
            AuditCategory.DECISION:        AuditEntityType.DECISION,
            AuditCategory.CLARIFICATION:   AuditEntityType.CLARIFICATION,
            AuditCategory.ERROR:           AuditEntityType.SYSTEM,
        }

        return AuditLog(
            # Standard fields
            entity_type=entity_type_map.get(record.category, AuditEntityType.SYSTEM),
            entity_id=record.document_id or record.policy_id or record.attempt_id,
            action=action_map.get(record.category, AuditAction.UPDATE),
            description=record.action[:500] if record.action else None,
            actor_type=actor_type_map.get(
                record.audit_ctx.actor_type.value, ActorType.SYSTEM
            ),
            actor_id=record.audit_ctx.user_id,
            actor_name=record.audit_ctx.actor_name,
            previous_state=record.previous_state,
            new_state=record.new_state,
            changed_fields=record.changed_fields or None,
            request_id=record.audit_ctx.request_id,
            trace_id=record.audit_ctx.trace_id,
            ip_address=record.audit_ctx.actor_ip,
            user_agent=record.audit_ctx.actor_user_agent,
            case_id=record.case_id,
            # Extended fields (new columns added in migration)
            audit_category=record.category.value,
            audit_severity=record.severity.value,
            occurred_at=record.occurred_at,
            duration_ms=record.duration_ms,
            session_id=record.audit_ctx.session_id,
            document_id=record.document_id,
            policy_id=record.policy_id,
            attempt_id=record.attempt_id,
            event_data=record.event_data,
            error_type=record.error_type,
            error_message=record.error_message,
            error_hash=record.error_hash,
            content_hash=record.content_hash,
            metadata_={
                "event_id":  record.event_id,
                "log_data":  record.log_data,
            },
        )

    async def close(self) -> None:
        pass  # Session factory lifecycle managed by app startup/shutdown


# ---------------------------------------------------------------------------
# 2. Structlog backend
# ---------------------------------------------------------------------------

class StructlogAuditStorage(AuditStorageBackend):
    """
    Emits one structured log entry per audit record.

    Uses PII-masked log_data — safe for ELK/CloudWatch/Datadog ingestion.
    Severity is mapped to the appropriate log level.
    """

    _LEVEL_MAP = {
        AuditSeverity.DEBUG:    "debug",
        AuditSeverity.INFO:     "info",
        AuditSeverity.WARNING:  "warning",
        AuditSeverity.ERROR:    "error",
        AuditSeverity.CRITICAL: "critical",
    }

    async def write(self, record: AuditRecord) -> None:
        level = self._LEVEL_MAP.get(record.severity, "info")
        log_dict = record.to_log_dict()
        bound = logger.bind(**log_dict)
        getattr(bound, level)("audit.event")

    async def write_batch(self, records: list[AuditRecord]) -> None:
        for record in records:
            await self.write(record)

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Composite backend
# ---------------------------------------------------------------------------

class CompositeAuditStorage(AuditStorageBackend):
    """
    Writes to all configured backends in sequence.

    A failure in one backend does NOT prevent writes to subsequent backends.
    Errors are logged but never propagated to callers.
    """

    def __init__(self, backends: list[AuditStorageBackend]) -> None:
        self._backends = backends

    async def write(self, record: AuditRecord) -> None:
        await self.write_batch([record])

    async def write_batch(self, records: list[AuditRecord]) -> None:
        for backend in self._backends:
            try:
                await backend.write_batch(records)
            except Exception as exc:
                logger.error(
                    "audit.composite_storage.backend_failed",
                    backend=type(backend).__name__,
                    count=len(records),
                    error=str(exc),
                )

    async def close(self) -> None:
        for backend in self._backends:
            try:
                await backend.close()
            except Exception:
                pass

    @classmethod
    def default(cls) -> "CompositeAuditStorage":
        """Build the default composite backend (DB + structlog)."""
        return cls(backends=[
            DatabaseAuditStorage(),
            StructlogAuditStorage(),
        ])
