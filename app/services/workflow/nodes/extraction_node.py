"""
Extraction node — Stage 2 of the PA review workflow.

Responsibilities:
  - Run the hybrid ExtractionEngine on every PROCESSED document
  - Populate extracted_entities in state (dict keyed by document_id)
  - Accumulate LLM token usage into tokens_used
  - Transition workflow phase to RETRIEVAL

Extraction is run concurrently across documents (bounded to 2 in-flight
LLM calls to avoid rate-limit exhaustion).

If extraction fails for a single document, that document is skipped and
a warning is emitted — the workflow continues with partial data rather
than failing entirely.  If ALL documents fail extraction, the workflow
transitions to FAILED.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from app.services.extraction.engine import ExtractionEngine
from app.services.extraction.models import ExtractionRequest
from app.services.workflow.nodes.base import BaseNode, NodeContext
from app.services.workflow.state import mutations
from app.services.workflow.state.models import (
    AuditEventType,
    DocumentStatus,
    WorkflowPhase,
)
from app.services.workflow.state.schema import PAWorkflowState

logger = structlog.get_logger(__name__)

# Concurrent extraction limit — balances throughput vs. OpenAI rate limits
_MAX_CONCURRENT = 2


class ExtractionNode(BaseNode):
    """Extract medical entities from all processed documents."""

    node_name = "extraction_node"

    def __init__(self) -> None:
        super().__init__()
        # Lazy-initialised so settings are resolved at runtime not import time
        self._engine: ExtractionEngine | None = None

    def _get_engine(self) -> ExtractionEngine:
        if self._engine is None:
            self._engine = ExtractionEngine.from_settings()
        return self._engine

    async def execute(
        self, state: PAWorkflowState, nctx: NodeContext
    ) -> dict[str, Any]:
        ctx = nctx.audit_ctx
        t0 = time.monotonic()

        processable = [
            d for d in state.get("raw_documents", [])
            if d.status == DocumentStatus.PROCESSED and d.content_text
        ]

        if not processable:
            nctx.log.warning("extraction_node.no_processable_documents")
            return mutations.with_error(
                "No processed documents with text content available",
                ctx,
                exc_type="ExtractionError",
            )

        nctx.log.info("extraction_node.starting", doc_count=len(processable))

        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
        tasks = [
            self._extract_one(doc.document_id, doc.content_text, semaphore, nctx)
            for doc in processable
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        entity_map: dict[str, Any] = {}
        total_tokens = 0
        failed_count = 0
        elapsed_ms = (time.monotonic() - t0) * 1000

        for doc, result in zip(processable, results):
            if isinstance(result, Exception):
                nctx.log.error(
                    "extraction_node.doc_failed",
                    document_id=doc.document_id,
                    error=str(result),
                )
                failed_count += 1
                continue

            extraction_result, tokens = result
            total_tokens += tokens

            from app.services.workflow.state.models import ExtractedEntities
            entity_map[doc.document_id] = ExtractedEntities(
                document_id=doc.document_id,
                patient=extraction_result.patient,
                provider=extraction_result.provider,
                diagnoses=extraction_result.diagnoses,
                icd_codes=extraction_result.icd_codes,
                cpt_codes=extraction_result.cpt_codes,
                medications=extraction_result.medications,
                glucose_readings=extraction_result.glucose_readings,
                hba1c_readings=extraction_result.hba1c_readings,
                insulin_regimens=extraction_result.insulin_regimens,
                lab_values=extraction_result.lab_values,
                symptoms=extraction_result.symptoms,
                treatment_history=extraction_result.treatment_history,
                complications=extraction_result.complications,
                overall_confidence=extraction_result.overall_confidence,
                grounding_pass_rate=extraction_result.grounding_pass_rate,
                extraction_method=extraction_result.extraction_method.value,
                llm_tokens_used=tokens,
            )

        if not entity_map:
            return mutations.with_error(
                f"Extraction failed for all {failed_count} document(s)",
                ctx,
                exc_type="ExtractionError",
            )

        return {
            "extracted_entities": entity_map,
            "tokens_used":        total_tokens,
            "processing_ms":      elapsed_ms,
            "workflow_phase":     WorkflowPhase.RETRIEVAL,
            **ctx.event(
                AuditEventType.ENTITIES_EXTRACTED,
                data={
                    "docs_extracted": len(entity_map),
                    "docs_failed": failed_count,
                    "total_tokens": total_tokens,
                    "icd_codes": list({
                        c.code
                        for e in entity_map.values()
                        for c in e.icd_codes
                    }),
                    "cpt_codes": list({
                        c.code
                        for e in entity_map.values()
                        for c in e.cpt_codes
                    }),
                },
                duration_ms=elapsed_ms,
            ),
        }

    async def _extract_one(
        self,
        document_id: str,
        text: str,
        semaphore: asyncio.Semaphore,
        nctx: NodeContext,
    ):
        """Run extraction on a single document.  Returns (ExtractionResult, tokens)."""
        async with semaphore:
            engine = self._get_engine()
            request = ExtractionRequest(
                document_id=document_id,
                text=text,
                run_icd_validation=True,
                run_cpt_validation=True,
            )
            result = await engine.extract(request)
            return result, result.llm_tokens_used


# Module-level callable
extraction_node = ExtractionNode()
