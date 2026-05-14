"""
Hybrid RAG retrieval orchestrator.

Coordinates all retrieval strategies into a single ranked result list:

  Stage 1 — Parallel retrieval
    ├── semantic_search()   dense vector similarity (Pinecone)
    ├── hybrid_search()     dense + BM25 sparse (Pinecone native hybrid)
    ├── CPTRetriever        CPT code hierarchy expansion + hybrid search
    └── ICDRetriever        ICD-10 hierarchy expansion + hybrid search

  Stage 2 — Fusion
    └── RRF fusion          Reciprocal Rank Fusion across all result lists

  Stage 3 — Scoring
    └── RelevanceScorer     Multi-signal: vector_sim, code_match, temporal, payer

  Stage 4 — Reranking
    └── RerankerPipeline    Cohere reranker (with score-fusion fallback)

  Stage 5 — Grouping
    └── group_into_policies  chunk → policy aggregation (top-N policies)

  Stage 6 — Evaluation (optional)
    └── RetrievalEvaluator  Proxy metrics for Prometheus / logging

Result type: list[RetrievedPolicy] — ready for the reasoning node.

Usage:
    orchestrator = HybridRetrievalOrchestrator.from_settings()
    policies = await orchestrator.retrieve(
        query="CGM coverage type 2 diabetes",
        cpt_codes=["95249"],
        icd_codes=["E11.9"],
        top_k=5,
    )
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from app.services.retrieval.cpt_retriever import CPTRetriever
from app.services.retrieval.evaluator import RetrievalEvaluator, RetrievalMetrics
from app.services.retrieval.fusion import RRFFusion, normalize_scores
from app.services.retrieval.icd_retriever import ICDRetriever
from app.services.retrieval.reranker import RerankerPipeline
from app.services.retrieval.scorer import RelevanceScorer, ScorerConfig
from app.services.vector.retrieval import RetrievalService
from app.services.vector.schemas import RetrievalMatch

logger = structlog.get_logger(__name__)

# How many chunks to over-fetch from each strategy before fusion
_STRATEGY_TOP_K_MULTIPLIER = 3

# Maximum policies to return after grouping
DEFAULT_TOP_POLICIES = 8

# Maximum chunks per policy to keep after grouping
MAX_CHUNKS_PER_POLICY = 5

# Minimum number of chunks a policy must have to be included
MIN_CHUNKS_PER_POLICY = 1


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class OrchestratorConfig:
    """
    Configuration for the hybrid retrieval orchestrator.

    Strategy weights affect RRF fusion: a higher weight amplifies that
    strategy's contribution without changing its individual rankings.
    """
    # Strategy toggle
    enable_semantic:  bool = True
    enable_hybrid:    bool = True
    enable_cpt:       bool = True
    enable_icd:       bool = True

    # RRF fusion weights per strategy
    semantic_weight:  float = 1.0
    hybrid_weight:    float = 1.5   # hybrid is typically most accurate
    cpt_weight:       float = 1.2
    icd_weight:       float = 1.1

    # Scoring
    scorer_config: ScorerConfig = field(default_factory=ScorerConfig)

    # Reranking
    rerank_enabled:   bool = True
    top_n_rerank:     int = 20       # rerank at most this many before trimming

    # Output
    top_policies:     int = DEFAULT_TOP_POLICIES
    max_chunks:       int = MAX_CHUNKS_PER_POLICY

    # Evaluation
    run_proxy_eval:   bool = True


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class OrchestratorResult:
    """
    Full result from the hybrid retrieval orchestrator.

    Includes the final ranked RetrievedPolicy objects plus debug data.
    """
    policies: list[Any]   # list[RetrievedPolicy] — avoids circular import
    fused_matches: list[RetrievalMatch]
    strategy_counts: dict[str, int]
    proxy_metrics: RetrievalMetrics | None
    total_latency_ms: float
    query: str
    cpt_codes: list[str]
    icd_codes: list[str]


# ---------------------------------------------------------------------------
# Policy grouping (chunk → policy aggregation)
# ---------------------------------------------------------------------------

def _group_into_policies(
    matches: list[RetrievalMatch],
    query: str,
    max_policies: int = DEFAULT_TOP_POLICIES,
    max_chunks: int = MAX_CHUNKS_PER_POLICY,
) -> list[Any]:
    """
    Group ranked chunks into policy-level results.

    Groups by (policy_id, policy_version), takes the top-N chunks per policy
    by score, and computes the average score across chunks.

    Returns list[RetrievedPolicy] — imported lazily to avoid circular imports.
    """
    from datetime import UTC, datetime
    from app.services.workflow.state.models import PolicyChunk, RetrievedPolicy

    # Group by dedup key (policy_id + version)
    groups: dict[str, list[RetrievalMatch]] = {}
    for m in matches:
        key = f"{m.metadata.policy_id}::{m.metadata.policy_version}"
        groups.setdefault(key, []).append(m)

    policies: list[tuple[float, RetrievedPolicy]] = []
    for key, chunks in groups.items():
        # Sort chunks by score, take top-N
        top_chunks = sorted(chunks, key=lambda m: m.score, reverse=True)[:max_chunks]
        avg_score = sum(c.score for c in top_chunks) / len(top_chunks)

        # Build PolicyChunk objects
        policy_chunks = [
            PolicyChunk(
                chunk_id=c.vector_id,
                criterion_text=c.metadata.chunk_text,
                criterion_type="coverage_criteria",
                section_header=None,
                page_number=c.metadata.chunk_index,
                similarity_score=c.score,
                metadata={
                    "policy_version": c.metadata.policy_version,
                    "effective_date": c.metadata.effective_date,
                },
            )
            for c in top_chunks
        ]

        first = top_chunks[0].metadata
        policy = RetrievedPolicy(
            policy_id=first.policy_id,
            policy_version=first.policy_version,
            payer_name=first.payer_name or "",
            service_type=first.service_type or "",
            cpt_codes=list(first.cpt_codes),
            icd_codes=list(first.icd_codes),
            similarity_score=avg_score,
            criteria_chunks=policy_chunks,
            retrieved_at=datetime.now(UTC),
            retrieval_query=query,
            namespace="",
        )
        policies.append((avg_score, policy))

    # Sort by avg score descending, return top N
    policies.sort(key=lambda t: t[0], reverse=True)
    return [p for _, p in policies[:max_policies]]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class HybridRetrievalOrchestrator:
    """
    Coordinates all retrieval strategies into a single ranked result.

    Designed to be called once per workflow execution from retrieval_node.
    Thread-safe — multiple concurrent cases share the same instance.

    Args:
        retrieval_service:  Base RetrievalService (Pinecone + embeddings).
        reranker:           RerankerPipeline (Cohere + fallback).
        config:             OrchestratorConfig tuning knobs.
    """

    def __init__(
        self,
        retrieval_service: RetrievalService,
        reranker: RerankerPipeline,
        config: OrchestratorConfig | None = None,
    ) -> None:
        self._svc = retrieval_service
        self._reranker = reranker
        self._cfg = config or OrchestratorConfig()
        self._cpt_retriever = CPTRetriever(retrieval_service)
        self._icd_retriever = ICDRetriever(retrieval_service)
        self._scorer = RelevanceScorer(self._cfg.scorer_config)
        self._fusion = RRFFusion(
            weights=[
                self._cfg.semantic_weight,
                self._cfg.hybrid_weight,
                self._cfg.cpt_weight,
                self._cfg.icd_weight,
            ]
        )
        self._log = structlog.get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        query: str,
        cpt_codes: list[str] | None = None,
        icd_codes: list[str] | None = None,
        *,
        payer_name: str | None = None,
        service_type: str | None = None,
        namespace: str | None = None,
        top_k: int | None = None,
    ) -> OrchestratorResult:
        """
        Run the full hybrid retrieval pipeline.

        Args:
            query:        Clinical question or case summary.
            cpt_codes:    CPT procedure codes from extracted entities.
            icd_codes:    ICD-10 diagnosis codes from extracted entities.
            payer_name:   Payer to restrict results to.
            service_type: Service category (e.g. "Continuous Glucose Monitor").
            namespace:    Pinecone namespace override.
            top_k:        Number of policies to return (default from config).

        Returns:
            OrchestratorResult with ranked policies and debug data.
        """
        t0 = time.perf_counter()
        cpt_codes = cpt_codes or []
        icd_codes = icd_codes or []
        top_k = top_k or self._cfg.top_policies
        fetch_k = top_k * _STRATEGY_TOP_K_MULTIPLIER

        self._log.info(
            "orchestrator.retrieve_started",
            query_len=len(query),
            cpt_count=len(cpt_codes),
            icd_count=len(icd_codes),
            top_k=top_k,
        )

        # ------------------------------------------------------------------
        # Stage 1: Parallel retrieval
        # ------------------------------------------------------------------
        strategy_tasks: list[asyncio.Task] = []
        strategy_names: list[str] = []

        if self._cfg.enable_semantic:
            strategy_tasks.append(asyncio.create_task(
                self._run_semantic(query, cpt_codes, icd_codes, fetch_k, payer_name, namespace),
                name="semantic",
            ))
            strategy_names.append("semantic")

        if self._cfg.enable_hybrid:
            strategy_tasks.append(asyncio.create_task(
                self._run_hybrid(query, cpt_codes, icd_codes, fetch_k, payer_name, namespace),
                name="hybrid",
            ))
            strategy_names.append("hybrid")

        if self._cfg.enable_cpt and cpt_codes:
            strategy_tasks.append(asyncio.create_task(
                self._run_cpt(query, cpt_codes, icd_codes, fetch_k, payer_name, namespace),
                name="cpt",
            ))
            strategy_names.append("cpt")

        if self._cfg.enable_icd and icd_codes:
            strategy_tasks.append(asyncio.create_task(
                self._run_icd(query, icd_codes, cpt_codes, fetch_k, payer_name, namespace),
                name="icd",
            ))
            strategy_names.append("icd")

        raw_results = await asyncio.gather(*strategy_tasks, return_exceptions=True)

        # Collect successful results, log failures
        ranked_lists: list[list[RetrievalMatch]] = []
        active_names: list[str] = []
        strategy_counts: dict[str, int] = {}

        for name, result in zip(strategy_names, raw_results):
            if isinstance(result, Exception):
                self._log.warning(
                    "orchestrator.strategy_failed",
                    strategy=name,
                    error=str(result),
                )
                strategy_counts[name] = 0
            else:
                matches = result or []
                strategy_counts[name] = len(matches)
                if matches:
                    ranked_lists.append(normalize_scores(matches))
                    active_names.append(name)

        if not ranked_lists:
            self._log.warning("orchestrator.all_strategies_failed")
            return OrchestratorResult(
                policies=[],
                fused_matches=[],
                strategy_counts=strategy_counts,
                proxy_metrics=None,
                total_latency_ms=(time.perf_counter() - t0) * 1000,
                query=query,
                cpt_codes=cpt_codes,
                icd_codes=icd_codes,
            )

        # ------------------------------------------------------------------
        # Stage 2: RRF Fusion
        # ------------------------------------------------------------------
        active_weights = self._active_weights(active_names)
        fusion = RRFFusion(weights=active_weights)
        fused = fusion.fuse(ranked_lists, list_names=active_names)

        self._log.debug(
            "orchestrator.fusion_complete",
            strategies=active_names,
            fused_count=len(fused),
        )

        # ------------------------------------------------------------------
        # Stage 3: Multi-signal scoring
        # ------------------------------------------------------------------
        scored = self._scorer.score_all(
            fused,
            cpt_codes=cpt_codes,
            icd_codes=icd_codes,
            payer_name=payer_name,
            service_type=service_type,
        )

        # ------------------------------------------------------------------
        # Stage 4: Reranking
        # ------------------------------------------------------------------
        rerank_input = scored[:self._cfg.top_n_rerank]
        if self._cfg.rerank_enabled:
            reranked = await self._reranker.rerank(
                query=query,
                matches=rerank_input,
                top_n=self._cfg.top_n_rerank,
            )
        else:
            reranked = rerank_input

        # ------------------------------------------------------------------
        # Stage 5: Group into policies
        # ------------------------------------------------------------------
        policies = _group_into_policies(
            reranked,
            query=query,
            max_policies=top_k,
            max_chunks=self._cfg.max_chunks,
        )

        # ------------------------------------------------------------------
        # Stage 6: Proxy evaluation (for monitoring)
        # ------------------------------------------------------------------
        proxy_metrics: RetrievalMetrics | None = None
        if self._cfg.run_proxy_eval and reranked:
            proxy_metrics = RetrievalEvaluator.evaluate_proxy(
                reranked,
                k=min(5, len(reranked)),
                query_cpt_codes=cpt_codes,
                query_icd_codes=icd_codes,
            )
            self._track_eval_metrics(proxy_metrics)

        total_ms = (time.perf_counter() - t0) * 1000
        self._log.info(
            "orchestrator.retrieve_complete",
            policies_returned=len(policies),
            total_latency_ms=round(total_ms, 1),
            strategy_counts=strategy_counts,
            **(proxy_metrics.to_dict() if proxy_metrics else {}),
        )

        return OrchestratorResult(
            policies=policies,
            fused_matches=reranked,
            strategy_counts=strategy_counts,
            proxy_metrics=proxy_metrics,
            total_latency_ms=total_ms,
            query=query,
            cpt_codes=cpt_codes,
            icd_codes=icd_codes,
        )

    # ------------------------------------------------------------------
    # Individual strategy runners (isolated for error handling)
    # ------------------------------------------------------------------

    async def _run_semantic(self, query, cpt_codes, icd_codes, k, payer_name, namespace):
        result = await self._svc.semantic_search(
            query, cpt_codes=cpt_codes, icd_codes=icd_codes,
            top_k=k, payer_name=payer_name, namespace=namespace,
        )
        return result.matches

    async def _run_hybrid(self, query, cpt_codes, icd_codes, k, payer_name, namespace):
        result = await self._svc.hybrid_search(
            query, cpt_codes=cpt_codes, icd_codes=icd_codes,
            top_k=k, payer_name=payer_name, namespace=namespace,
        )
        return result.matches

    async def _run_cpt(self, query, cpt_codes, icd_codes, k, payer_name, namespace):
        result = await self._cpt_retriever.retrieve(
            query, cpt_codes, icd_codes=icd_codes,
            top_k=k, payer_name=payer_name, namespace=namespace,
        )
        return result.matches

    async def _run_icd(self, query, icd_codes, cpt_codes, k, payer_name, namespace):
        result = await self._icd_retriever.retrieve(
            query, icd_codes, cpt_codes=cpt_codes,
            top_k=k, payer_name=payer_name, namespace=namespace,
        )
        return result.matches

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _active_weights(self, active_names: list[str]) -> list[float]:
        """Return per-strategy weights for the active strategies only."""
        weight_map = {
            "semantic": self._cfg.semantic_weight,
            "hybrid":   self._cfg.hybrid_weight,
            "cpt":      self._cfg.cpt_weight,
            "icd":      self._cfg.icd_weight,
        }
        return [weight_map.get(name, 1.0) for name in active_names]

    def _track_eval_metrics(self, metrics: RetrievalMetrics) -> None:
        try:
            from app.monitoring.metrics import (
                RETRIEVAL_PRECISION_AT_K,
                RETRIEVAL_NDCG_AT_K,
                RETRIEVAL_RESULTS_COUNT,
            )
            RETRIEVAL_PRECISION_AT_K.observe(metrics.precision_at_k)
            RETRIEVAL_NDCG_AT_K.observe(metrics.ndcg_at_k)
            RETRIEVAL_RESULTS_COUNT.observe(metrics.num_retrieved)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(
        cls,
        config: OrchestratorConfig | None = None,
    ) -> "HybridRetrievalOrchestrator":
        """
        Build an orchestrator from application settings.

        Creates all sub-services from environment configuration.
        """
        from app.services.vector.embeddings import EmbeddingService
        from app.services.vector.pinecone_client import PineconeClient
        from app.services.caching.retrieval_cache import RetrievalCache

        client = PineconeClient.from_settings()
        embeddings = EmbeddingService.from_settings()
        cache = RetrievalCache()
        retrieval_svc = RetrievalService(client, embeddings, cache)
        reranker = RerankerPipeline.from_settings()

        return cls(
            retrieval_service=retrieval_svc,
            reranker=reranker,
            config=config,
        )
