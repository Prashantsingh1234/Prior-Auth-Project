"""
Ingestion worker — processes IngestionTask messages.

Pipeline executed for each task:
  1. Fetch document bytes from secure storage (or download from URL)
  2. Persist metadata to DB (idempotent on document_id)
  3. Enqueue an OCRTask to pa.ocr for the actual extraction
  4. Emit audit event

The worker does NOT run OCR itself — it kicks off the OCR task so that
OCR and ingestion can scale independently.
"""

from __future__ import annotations

import structlog

from app.queues.consumer import BaseConsumer
from app.queues.models import AnyTask, IngestionTask, OCRTask
from app.queues.topology import QUEUE_SPECS
from app.monitoring.metrics import METRICS

logger = structlog.get_logger(__name__)


class IngestionWorker(BaseConsumer):

    queue_spec = QUEUE_SPECS["ingestion"]

    async def process(self, task: AnyTask) -> None:
        assert isinstance(task, IngestionTask), f"Expected IngestionTask, got {type(task)}"
        log = logger.bind(
            task_id=task.task_id,
            document_id=task.document_id,
            case_id=task.case_id,
        )
        log.info("ingestion_worker.started")

        # 1. Validate / fetch document
        doc_bytes = await self._fetch_document(task)

        # 2. Persist ingestion record (idempotent)
        await self._persist_ingestion_record(task, len(doc_bytes))

        # 3. Enqueue OCR task
        await self._enqueue_ocr(task, doc_bytes)

        # 4. Audit
        await self._emit_audit(task)

        METRICS.document_ingestion_total.labels(
            document_type=task.document_type, status="queued_for_ocr"
        ).inc()

        log.info("ingestion_worker.completed", bytes=len(doc_bytes))

    # ------------------------------------------------------------------

    async def _fetch_document(self, task: IngestionTask) -> bytes:
        """
        Retrieve raw document bytes.  Prefers secure storage; falls back to URL.
        Returns bytes or raises if unavailable.
        """
        try:
            from app.security import get_secure_document_storage
            storage = get_secure_document_storage()
            content = await storage.retrieve(
                doc_id=task.document_id,
                caller_id=task.owner_id or "system",
                caller_role="admin",
            )
            if content is not None:
                logger.debug("ingestion_worker.fetched_from_storage", doc_id=task.document_id)
                return content
        except Exception as exc:
            logger.debug("ingestion_worker.storage_miss", doc_id=task.document_id, error=str(exc))

        if task.document_url:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(task.document_url)
                resp.raise_for_status()
                logger.debug("ingestion_worker.fetched_from_url", url=task.document_url)
                return resp.content

        raise ValueError(
            f"Document {task.document_id!r} not found in storage and no URL provided"
        )

    async def _persist_ingestion_record(self, task: IngestionTask, byte_count: int) -> None:
        """Write ingestion metadata to DB (upsert on document_id)."""
        try:
            from app.db.session.database import get_db_session
            async with get_db_session() as session:
                from sqlalchemy import text
                await session.execute(
                    text(
                        "INSERT INTO document_ingestion_log "
                        "(document_id, document_type, owner_id, byte_count, status, task_id) "
                        "VALUES (:did, :dtype, :owner, :bytes, 'QUEUED', :tid) "
                        "ON DUPLICATE KEY UPDATE status='QUEUED', task_id=:tid"
                    ),
                    {
                        "did":   task.document_id,
                        "dtype": task.document_type,
                        "owner": task.owner_id or "",
                        "bytes": byte_count,
                        "tid":   task.task_id,
                    },
                )
                await session.commit()
        except Exception as exc:
            # DB write failure is logged but does not block OCR enqueue
            logger.warning(
                "ingestion_worker.db_persist_failed",
                doc_id=task.document_id,
                error=str(exc),
            )

    async def _enqueue_ocr(self, task: IngestionTask, doc_bytes: bytes) -> None:
        """Hand off to the OCR worker queue."""
        from app.queues.publisher import get_publisher
        publisher = await get_publisher()
        ocr_task = OCRTask(
            case_id=task.case_id,
            document_id=task.document_id,
            storage_path=f"documents/{task.document_id}",
            document_type=task.document_type,
            metadata={"ingestion_task_id": task.task_id},
        )
        await publisher.publish(ocr_task)
        logger.debug("ingestion_worker.ocr_enqueued", doc_id=task.document_id)

    async def _emit_audit(self, task: IngestionTask) -> None:
        try:
            from app.guardrails.audit import _write_to_audit_db
            await _write_to_audit_db(
                event_type="DOCUMENT_INGESTED",
                actor_id=task.owner_id or "system",
                case_id=task.case_id,
                event_data={"document_id": task.document_id, "task_id": task.task_id},
                severity="LOW",
            )
        except Exception:
            pass
