"""
Retrieval node — Stage 3 of the PA review workflow.

Responsibilities:
  - Build a clinical query from extracted entities (ICD codes, CPT codes,
    diagnoses, symptoms, medications, service type)
  - Run hybrid dense+sparse search against the Pinecone policy index
  - Map raw RetrievalMatch results → RetrievedPolicy workflow models
  - Populate retrieved_policies in state
  - Transition workflow phase to EVALUATION (reasoning)

Query construction strategy:
  - Primary query: diagnoses + service type as natural language
  - Metadata filters: CPT codes + ICD codes (Pinecone $in filters)
  - Payer filter: applied if payer_id is set in state

If a prior clarification round added new context, the retrieval node is
re-run with the enriched clinical text so the reasoning node sees
policies relevant to the updated information.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from app.services.workflow.nodes.base import BaseNode, NodeContext
from app.services.workflow.state import mutations
from app.services.workflow.state.models import (
    AuditEventType,
    PolicyChunk,
    RetrievedPolicy,
    WorkflowPhase,
)
from app.services.workflow.state.schema import (
    PAWorkflowState,
    combined_cpt_codes,
    combined_icd_codes,
)

logger = structlog.get_logger(__name__)

_TOP_K = 8          # Max policies to retrieve
_MAX_CHUNKS_PER_POLICY = 5  # Keep top-5 chunks per policy


class RetrievalNode(BaseNode):
    """Retrieve relevant insurance policy criteria from the vector store."""

    node_name = "retrieval_node"

    def __init__(self) -> None:
        super().__init__()
        self._retrieval_service = None

    def _get_service(self):
        if self._retrieval_service is None:
            from app.services.vector.pinecone_client import get_pinecone_client
            from app.services.vector.embeddings import EmbeddingService
            from app.services.vector.retrieval import RetrievalService
            self._retrieval_service = RetrievalService(
                client=get_pinecone_client(),
                embedding_service=EmbeddingService.from_settings(),
            )
        return self._retrieval_service

    async def execute(
        self, state: PAWorkflowState, nctx: NodeContext
    ) -> dict[str, Any]:
        ctx = nctx.audit_ctx
        t0  = time.monotonic()

        # Build query from extracted clinical data
        query = self._build_query(state)
        icd_codes = combined_icd_codes(state)
        cpt_codes = combined_cpt_codes(state)
        payer_id  = state.get("payer_id")

        nctx.log.info(
            "retrieval_node.querying",
            query_preview=query[:80],
            icd_count=len(icd_codes),
            cpt_count=len(cpt_codes),
        )

        try:
            service = self._get_service()
            result = await service.hybrid_search(
                query=query,
                cpt_codes=cpt_codes or None,
                icd_codes=icd_codes or None,
                payer_name=payer_id,
                top_k=_TOP_K * 3,  # over-fetch, then group + trim
                use_cache=True,
            )
        except Exception as exc:
            nctx.log.error("retrieval_node.search_failed", error=str(exc))
            return mutations.with_error(str(exc), ctx, exc_type=type(exc).__name__)

        elapsed_ms = (time.monotonic() - t0) * 1000

        policies = self._group_into_policies(result.matches)

        nctx.log.info(
            "retrieval_node.complete",
            policies_found=len(policies),
            elapsed_ms=round(elapsed_ms, 1),
        )

        return {
            "retrieved_policies": policies,
            "processing_ms":      elapsed_ms,
            "workflow_phase":     WorkflowPhase.EVALUATION,
            **ctx.event(
                AuditEventType.POLICIES_RETRIEVED,
                data={
                    "query":          query[:120],
                    "total_matches":  result.total_matches,
                    "policies":       len(policies),
                    "retrieval_type": result.retrieval_type,
                    "latency_ms":     result.latency_ms,
                },
                duration_ms=elapsed_ms,
            ),
        }

    # ------------------------------------------------------------------
    # Query builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_query(state: PAWorkflowState) -> str:
        """
        Construct a natural-language retrieval query from extracted entities.

        Priority: diagnoses > service_type > ICD descriptions > medications
        """
        parts: list[str] = []

        service_type = state.get("service_type")
        if service_type:
            parts.append(service_type)

        for entities in state.get("extracted_entities", {}).values():
            for diag in entities.diagnoses[:3]:
                if diag.name:
                    parts.append(diag.name)
            for med in entities.medications[:2]:
                if med.name:
                    parts.append(f"{med.name} treatment")
            if not parts:
                for sym in entities.symptoms[:2]:
                    if sym.name:
                        parts.append(sym.name)

        icd_codes = combined_icd_codes(state)
        cpt_codes = combined_cpt_codes(state)
        if icd_codes:
            parts.append(f"ICD {' '.join(icd_codes[:3])}")
        if cpt_codes:
            parts.append(f"CPT {' '.join(cpt_codes[:3])}")

        if not parts:
            parts.append("prior authorization medical coverage criteria")

        return " ".join(parts)[:512]

    # ------------------------------------------------------------------
    # Group raw matches into RetrievedPolicy objects
    # ------------------------------------------------------------------

    @staticmethod
    def _group_into_policies(matches) -> list[RetrievedPolicy]:
        """
        Group individual chunk matches by policy_id + policy_version.

        Each RetrievedPolicy aggregates the top-K chunks from that policy,
        sorted by similarity score.
        """
        from collections import defaultdict
        policy_chunks: dict[str, list] = defaultdict(list)
        policy_meta: dict[str, Any] = {}

        for match in matches:
            meta = match.metadata
            key  = f"{meta.policy_id}::{meta.policy_version}"
            policy_chunks[key].append(match)
            if key not in policy_meta:
                policy_meta[key] = meta

        policies: list[RetrievedPolicy] = []
        for key, chunk_matches in policy_chunks.items():
            meta = policy_meta[key]
            # Sort by score, take top-K
            top_chunks = sorted(chunk_matches, key=lambda m: m.score, reverse=True)[:_MAX_CHUNKS_PER_POLICY]
            avg_score  = sum(m.score for m in top_chunks) / max(len(top_chunks), 1)

            chunks = []
            for i, cm in enumerate(top_chunks):
                m = cm.metadata
                chunks.append(PolicyChunk(
                    chunk_id=cm.vector_id,
                    criterion_text=getattr(m, "chunk_text", getattr(m, "criterion_text", "")),
                    criterion_type=getattr(m, "criterion_type", None),
                    section_header=getattr(m, "section_header", None),
                    page_number=getattr(m, "page_number", None),
                    similarity_score=cm.score,
                ))

            policies.append(RetrievedPolicy(
                policy_id=meta.policy_id,
                policy_version=meta.policy_version,
                payer_name=getattr(meta, "payer_name", None),
                service_type=getattr(meta, "service_type", None),
                cpt_codes=getattr(meta, "cpt_codes", []),
                icd_codes=getattr(meta, "icd_codes", []),
                similarity_score=avg_score,
                criteria_chunks=chunks,
                retrieval_query=key,
            ))

        return sorted(policies, key=lambda p: p.similarity_score, reverse=True)[:_TOP_K]


# Module-level callable
retrieval_node = RetrievalNode()
