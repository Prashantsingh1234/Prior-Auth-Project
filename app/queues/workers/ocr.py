"""
OCR worker — processes OCRTask messages.

Execution:
  1. Retrieve document bytes from secure storage
  2. Run OCR (Azure primary → PaddleOCR fallback on low confidence)
  3. Persist extraction result to DB
  4. Enqueue EmbeddingTask for each extracted text chunk
  5. Update document ingestion log status
  6. Emit Prometheus OCR metrics
"""

from __future__ import annotations

import structlog

from app.queues.consumer import BaseConsumer
from app.queues.models import AnyTask, EmbeddingTask, OCRTask
from app.queues.topology import QUEUE_SPECS
from app.monitoring.metrics import METRICS

logger = structlog.get_logger(__name__)

_CHUNK_SIZE = 512  # characters per embedding chunk


class OCRWorker(BaseConsumer):

    queue_spec = QUEUE_SPECS["ocr"]

    async def process(self, task: AnyTask) -> None:
        assert isinstance(task, OCRTask), f"Expected OCRTask, got {type(task)}"
        log = logger.bind(
            task_id=task.task_id,
            document_id=task.document_id,
            case_id=task.case_id,
        )
        log.info("ocr_worker.started", provider=task.preferred_provider)

        # 1. Fetch document
        doc_bytes = await self._fetch(task)

        # 2. Run OCR
        extraction = await self._run_ocr(task, doc_bytes)

        # 3. Persist result
        await self._persist_extraction(task, extraction)

        # 4. Enqueue embeddings
        await self._enqueue_embeddings(task, extraction["text"])

        # 5. Update ingestion status
        await self._update_status(task, "OCR_COMPLETE")

        METRICS.ocr_requests_total.labels(
            provider=extraction["provider"], outcome="success"
        ).inc()
        METRICS.ocr_confidence.labels(provider=extraction["provider"]).observe(
            extraction["confidence"]
        )

        log.info(
            "ocr_worker.completed",
            provider=extraction["provider"],
            confidence=round(extraction["confidence"], 3),
            text_len=len(extraction["text"]),
        )

    # ------------------------------------------------------------------

    async def _fetch(self, task: OCRTask) -> bytes:
        from app.security import get_secure_document_storage
        storage = get_secure_document_storage()
        data = await storage.retrieve(
            doc_id=task.document_id,
            caller_id="system",
            caller_role="admin",
        )
        if data is None:
            raise FileNotFoundError(f"Document {task.document_id!r} not in secure storage")
        return data

    async def _run_ocr(self, task: OCRTask, doc_bytes: bytes) -> dict:
        """
        Run OCR via the existing OCR service.  Returns:
          {"text": str, "confidence": float, "provider": str, "pages": int}
        """
        try:
            from app.services.ocr import get_ocr_service
            svc = get_ocr_service()
            result = await svc.extract(
                document_bytes=doc_bytes,
                document_type=task.document_type,
                preferred_provider=task.preferred_provider,
                confidence_threshold=task.confidence_threshold,
            )
            return {
                "text":       result.text,
                "confidence": result.confidence,
                "provider":   result.provider,
                "pages":      result.page_count,
                "raw":        result.raw_response if hasattr(result, "raw_response") else {},
            }
        except Exception as exc:
            METRICS.ocr_requests_total.labels(
                provider=task.preferred_provider, outcome="failure"
            ).inc()
            raise

    async def _persist_extraction(self, task: OCRTask, extraction: dict) -> None:
        try:
            from app.db.session.database import get_db_session
            async with get_db_session() as session:
                from sqlalchemy import text
                await session.execute(
                    text(
                        "INSERT INTO ocr_extractions "
                        "(document_id, extracted_text, confidence_score, ocr_provider, page_count, task_id) "
                        "VALUES (:did, :txt, :conf, :prov, :pages, :tid) "
                        "ON DUPLICATE KEY UPDATE "
                        "  extracted_text=:txt, confidence_score=:conf, ocr_provider=:prov"
                    ),
                    {
                        "did":   task.document_id,
                        "txt":   extraction["text"][:65_535],  # MySQL TEXT limit guard
                        "conf":  extraction["confidence"],
                        "prov":  extraction["provider"],
                        "pages": extraction.get("pages", 0),
                        "tid":   task.task_id,
                    },
                )
                await session.commit()
        except Exception as exc:
            logger.warning("ocr_worker.persist_failed", doc_id=task.document_id, error=str(exc))

    async def _enqueue_embeddings(self, task: OCRTask, text: str) -> None:
        from app.queues.publisher import get_publisher
        publisher = await get_publisher()

        chunks = _chunk_text(text, _CHUNK_SIZE)
        embedding_tasks = [
            EmbeddingTask(
                case_id=task.case_id,
                document_id=task.document_id,
                chunk_id=f"{task.document_id}:{i}",
                text=chunk,
                vector_metadata={
                    "document_id":   task.document_id,
                    "chunk_index":   i,
                    "document_type": task.document_type,
                },
                metadata={"ocr_task_id": task.task_id},
            )
            for i, chunk in enumerate(chunks)
        ]
        await publisher.publish_many(embedding_tasks)
        logger.debug(
            "ocr_worker.embeddings_enqueued",
            doc_id=task.document_id,
            chunk_count=len(embedding_tasks),
        )

    async def _update_status(self, task: OCRTask, status: str) -> None:
        try:
            from app.db.session.database import get_db_session
            async with get_db_session() as session:
                from sqlalchemy import text
                await session.execute(
                    text(
                        "UPDATE document_ingestion_log SET status=:status "
                        "WHERE document_id=:did"
                    ),
                    {"status": status, "did": task.document_id},
                )
                await session.commit()
        except Exception as exc:
            logger.warning("ocr_worker.status_update_failed", error=str(exc))


def _chunk_text(text: str, chunk_size: int) -> list[str]:
    """Split text into overlapping chunks of roughly chunk_size characters."""
    overlap = chunk_size // 8
    chunks  = []
    start   = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start = end - overlap if end < len(text) else end
    return chunks
