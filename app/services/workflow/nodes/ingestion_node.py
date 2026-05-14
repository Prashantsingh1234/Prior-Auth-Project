"""
Ingestion node — Stage 1 of the PA review workflow.

Responsibilities:
  - Process every RawDocument with status=PENDING in state
  - Extract plain text from PDF bytes (pdfplumber) with OCR fallback
  - Store normalised text back into document.content_text
  - Mark each document PROCESSED (or FAILED on unrecoverable parse error)
  - Transition workflow phase to EXTRACTION

Dependencies used:
  - PDFParser from the ingestion pipeline  (if document is PDF)
  - DocumentNormalizer from the document pipeline (other formats)

A document that already has content_text set is treated as pre-processed
and is marked PROCESSED without re-parsing — supports both fresh and
pre-enriched document submissions.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any

import structlog

from app.services.workflow.nodes.base import BaseNode, NodeContext
from app.services.workflow.state import mutations
from app.services.workflow.state.models import (
    AuditEventType,
    DocumentStatus,
    RawDocument,
    WorkflowPhase,
)
from app.services.workflow.state.schema import PAWorkflowState

logger = structlog.get_logger(__name__)

# Minimum characters to consider a document successfully parsed
_MIN_TEXT_CHARS = 20


class IngestionNode(BaseNode):
    """
    Parse and normalise all pending documents in the workflow state.

    Skips documents that already have content_text set.
    Processes PDF, image, and text documents via the appropriate parser.
    """

    node_name = "ingestion_node"

    async def execute(
        self, state: PAWorkflowState, nctx: NodeContext
    ) -> dict[str, Any]:
        ctx = nctx.audit_ctx
        t0 = time.monotonic()

        pending = [
            d for d in state.get("raw_documents", [])
            if d.status == DocumentStatus.PENDING
        ]

        if not pending:
            nctx.log.warning("ingestion_node.no_pending_documents")
            return {
                **ctx.event(
                    AuditEventType.DOCUMENT_PARSED,
                    data={"pending_count": 0, "skipped": True},
                ),
            }

        nctx.log.info("ingestion_node.processing", count=len(pending))

        # Process documents concurrently — bounded at 3 to avoid overwhelming
        # the OCR / parse layer.
        semaphore = asyncio.Semaphore(3)
        tasks = [
            self._process_document(doc, semaphore, nctx)
            for doc in pending
        ]
        processed_docs: list[RawDocument] = await asyncio.gather(*tasks)

        elapsed_ms = (time.monotonic() - t0) * 1000

        failed = sum(1 for d in processed_docs if d.status == DocumentStatus.FAILED)
        ok     = sum(1 for d in processed_docs if d.status == DocumentStatus.PROCESSED)

        patch: dict[str, Any] = {
            "raw_documents":  processed_docs,
            "processing_ms":  elapsed_ms,
            "workflow_phase": WorkflowPhase.EXTRACTION,
            **ctx.event(
                AuditEventType.DOCUMENT_PARSED,
                data={
                    "total": len(processed_docs),
                    "processed": ok,
                    "failed": failed,
                },
                duration_ms=elapsed_ms,
            ),
        }

        if ok == 0:
            # All documents failed — transition to FAILED
            patch.update(
                mutations.with_error(
                    f"All {failed} document(s) failed to parse",
                    ctx,
                    exc_type="IngestionError",
                )
            )

        return patch

    async def _process_document(
        self,
        doc: RawDocument,
        semaphore: asyncio.Semaphore,
        nctx: NodeContext,
    ) -> RawDocument:
        async with semaphore:
            return await self._parse_single(doc, nctx)

    async def _parse_single(
        self, doc: RawDocument, nctx: NodeContext
    ) -> RawDocument:
        """Parse one document and return an updated copy."""
        # Already has text — no need to re-parse
        if doc.content_text and len(doc.content_text) >= _MIN_TEXT_CHARS:
            return doc.model_copy(update={
                "status": DocumentStatus.PROCESSED,
                "processed_at": datetime.utcnow(),
                "content": None,  # drop raw bytes
            })

        if not doc.content:
            return doc.model_copy(update={
                "status": DocumentStatus.FAILED,
                "error": "No content or content_text provided",
                "processed_at": datetime.utcnow(),
            })

        mime = doc.mime_type.lower()
        try:
            if "pdf" in mime:
                text, page_count = await self._parse_pdf(doc.content, nctx)
            elif any(img in mime for img in ("image/png", "image/jpeg", "image/tiff")):
                text, page_count = await self._parse_image(doc.content, nctx)
            elif "json" in mime:
                text = doc.content.decode("utf-8", errors="replace")
                page_count = 1
            else:
                text = doc.content.decode("utf-8", errors="replace")
                page_count = 1

            if not text or len(text) < _MIN_TEXT_CHARS:
                return doc.model_copy(update={
                    "status": DocumentStatus.FAILED,
                    "error": f"Extracted text too short ({len(text or '')} chars)",
                    "processed_at": datetime.utcnow(),
                })

            return doc.model_copy(update={
                "status": DocumentStatus.PROCESSED,
                "content_text": text,
                "page_count": page_count,
                "processed_at": datetime.utcnow(),
                "content": None,  # free raw bytes
            })

        except Exception as exc:
            nctx.log.error(
                "ingestion_node.parse_failed",
                document_id=doc.document_id,
                error=str(exc),
            )
            return doc.model_copy(update={
                "status": DocumentStatus.FAILED,
                "error": str(exc),
                "processed_at": datetime.utcnow(),
            })

    @staticmethod
    async def _parse_pdf(content: bytes, nctx: NodeContext) -> tuple[str, int]:
        """Extract text from PDF using pdfplumber with OCR fallback."""
        try:
            from app.services.ingestion.pdf_parser import PDFParser
            parser = PDFParser(ocr_enabled=True)
            parsed = await asyncio.to_thread(parser.parse_sync, content)
            return parsed.full_text, parsed.page_count
        except AttributeError:
            # parse_sync may not exist — use async API
            from app.services.ingestion.pdf_parser import PDFParser
            parser = PDFParser(ocr_enabled=True)
            parsed = await parser.parse(content)
            return parsed.full_text, parsed.page_count

    @staticmethod
    async def _parse_image(content: bytes, nctx: NodeContext) -> tuple[str, int]:
        """Extract text from an image using the OCR orchestrator."""
        from app.services.ocr.orchestrator import OCROrchestrator
        orchestrator = OCROrchestrator.from_settings()
        result = await orchestrator.process(
            content, mime_type="image/png", page_count=1
        )
        return result.full_text, 1


# Module-level callable — passed to graph.add_node("ingestion_node", ingestion_node)
ingestion_node = IngestionNode()
