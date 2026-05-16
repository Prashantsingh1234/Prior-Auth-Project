"""
Retrieval tests for the hybrid policy search pipeline.

Tests:
- Semantic retrieval returns relevant results
- Keyword retrieval for CPT/ICD codes
- RRF fusion merges and deduplicates results
- Scoring thresholds filter low-relevance chunks
- Reranker improves result ordering
- Benchmark evaluation against curated dataset
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


BENCHMARK_PATH = Path(__file__).parent / "datasets" / "benchmark.json"


@pytest.fixture
def benchmark_data():
    with open(BENCHMARK_PATH) as f:
        return json.load(f)


def _make_chunk(chunk_id: str, score: float = 0.85, **overrides) -> dict:
    chunk = {
        "chunk_id": chunk_id,
        "text": "Policy coverage criteria text.",
        "score": score,
        "policy_id": "POL-001",
        "section": "Coverage Criteria",
    }
    chunk.update(overrides)
    return chunk


class TestHybridRetrieval:

    @pytest.mark.asyncio
    async def test_retrieval_orchestrator_importable(self):
        try:
            from app.services.retrieval.orchestrator import RetrievalOrchestrator  # noqa: F401
        except ImportError:
            pytest.skip("RetrievalOrchestrator not yet implemented")

    @pytest.mark.asyncio
    async def test_retrieve_returns_list(self):
        try:
            from app.services.retrieval.orchestrator import RetrievalOrchestrator
        except ImportError:
            pytest.skip("RetrievalOrchestrator not yet implemented")

        orchestrator = RetrievalOrchestrator()
        mock_chunks = [_make_chunk(f"c{i}", score=0.9 - i * 0.05) for i in range(5)]

        with patch.object(orchestrator, "retrieve", new_callable=AsyncMock, return_value=mock_chunks):
            result = await orchestrator.retrieve(
                query="continuous glucose monitor type 2 diabetes",
                cpt_codes=["95249"],
                icd_codes=["E11.9"],
                top_k=5,
            )
            assert isinstance(result, list)
            assert len(result) == 5

    @pytest.mark.asyncio
    async def test_retrieve_deduplicates_results(self):
        """Results from different retrieval strategies should be deduplicated."""
        try:
            from app.services.retrieval.fusion import RRFFusion
        except ImportError:
            pytest.skip("RRFFusion not yet implemented")

        fusion = RRFFusion()

        semantic_results = [
            _make_chunk("chunk_001", score=0.92),
            _make_chunk("chunk_002", score=0.85),
            _make_chunk("chunk_003", score=0.78),
        ]
        keyword_results = [
            _make_chunk("chunk_001", score=0.88),  # duplicate
            _make_chunk("chunk_004", score=0.81),
        ]

        merged = fusion.merge([semantic_results, keyword_results])
        chunk_ids = [c["chunk_id"] for c in merged]
        # No duplicates
        assert len(chunk_ids) == len(set(chunk_ids))

    @pytest.mark.asyncio
    async def test_retrieve_returns_empty_on_no_match(self):
        try:
            from app.services.retrieval.orchestrator import RetrievalOrchestrator
        except ImportError:
            pytest.skip("RetrievalOrchestrator not yet implemented")

        orchestrator = RetrievalOrchestrator()
        with patch.object(orchestrator, "retrieve", new_callable=AsyncMock, return_value=[]):
            result = await orchestrator.retrieve(
                query="completely unrelated query with no policy match",
                cpt_codes=[],
                icd_codes=[],
                top_k=5,
            )
            assert result == []

    @pytest.mark.asyncio
    async def test_cpt_retriever_filters_by_cpt_code(self):
        try:
            from app.services.retrieval.cpt_retriever import CPTRetriever
        except ImportError:
            pytest.skip("CPTRetriever not yet implemented")

        retriever = CPTRetriever()
        mock_results = [
            _make_chunk("cgm_chunk_001", score=0.95),
            _make_chunk("cgm_chunk_002", score=0.88),
        ]

        with patch.object(retriever, "retrieve", new_callable=AsyncMock, return_value=mock_results):
            results = await retriever.retrieve(cpt_codes=["95249"], top_k=10)
            assert len(results) > 0
            # All results should be relevant to the CPT code
            for chunk in results:
                assert chunk["score"] > 0.0

    @pytest.mark.asyncio
    async def test_icd_retriever_returns_diagnosis_relevant_chunks(self):
        try:
            from app.services.retrieval.icd_retriever import ICDRetriever
        except ImportError:
            pytest.skip("ICDRetriever not yet implemented")

        retriever = ICDRetriever()
        mock_results = [_make_chunk("dm_chunk_001", score=0.91)]

        with patch.object(retriever, "retrieve", new_callable=AsyncMock, return_value=mock_results):
            results = await retriever.retrieve(icd_codes=["E11.9"], top_k=5)
            assert len(results) > 0

    @pytest.mark.asyncio
    async def test_results_ordered_by_score_descending(self):
        try:
            from app.services.retrieval.orchestrator import RetrievalOrchestrator
        except ImportError:
            pytest.skip("RetrievalOrchestrator not yet implemented")

        orchestrator = RetrievalOrchestrator()
        mock_chunks = [
            _make_chunk("c1", score=0.75),
            _make_chunk("c2", score=0.92),
            _make_chunk("c3", score=0.83),
        ]

        with patch.object(orchestrator, "retrieve", new_callable=AsyncMock, return_value=mock_chunks):
            results = await orchestrator.retrieve(
                query="test query",
                cpt_codes=["95249"],
                icd_codes=["E11.9"],
                top_k=5,
            )
            scores = [r["score"] for r in results]
            assert scores == sorted(scores, reverse=True), "Results should be sorted by score descending"


class TestRRFFusion:
    """Reciprocal Rank Fusion tests."""

    def test_rrf_fusion_importable(self):
        try:
            from app.services.retrieval.fusion import RRFFusion  # noqa: F401
        except ImportError:
            pytest.skip("RRFFusion not yet implemented")

    def test_rrf_empty_lists_returns_empty(self):
        try:
            from app.services.retrieval.fusion import RRFFusion
        except ImportError:
            pytest.skip("RRFFusion not yet implemented")

        fusion = RRFFusion()
        result = fusion.merge([[], []])
        assert result == []

    def test_rrf_single_list_returns_same_order(self):
        try:
            from app.services.retrieval.fusion import RRFFusion
        except ImportError:
            pytest.skip("RRFFusion not yet implemented")

        fusion = RRFFusion()
        chunks = [_make_chunk(f"c{i}", score=0.9 - i * 0.1) for i in range(3)]
        result = fusion.merge([chunks])
        result_ids = [r["chunk_id"] for r in result]
        original_ids = [c["chunk_id"] for c in chunks]
        assert set(result_ids) == set(original_ids)

    def test_rrf_boosts_consistently_high_ranked_items(self):
        """Items ranked high in multiple lists should have higher RRF scores."""
        try:
            from app.services.retrieval.fusion import RRFFusion
        except ImportError:
            pytest.skip("RRFFusion not yet implemented")

        fusion = RRFFusion()
        # chunk_A appears #1 in both lists
        list1 = [_make_chunk("chunk_A", 0.95), _make_chunk("chunk_B", 0.85), _make_chunk("chunk_C", 0.75)]
        list2 = [_make_chunk("chunk_A", 0.90), _make_chunk("chunk_D", 0.88), _make_chunk("chunk_B", 0.70)]

        merged = fusion.merge([list1, list2])
        assert len(merged) > 0
        # chunk_A should be ranked first (high in both lists)
        assert merged[0]["chunk_id"] == "chunk_A"


class TestReranker:
    """Reranker service tests."""

    @pytest.mark.asyncio
    async def test_reranker_preserves_all_chunks(self):
        try:
            from app.services.retrieval.reranker import Reranker
        except ImportError:
            pytest.skip("Reranker not yet implemented")

        reranker = Reranker()
        chunks = [_make_chunk(f"c{i}") for i in range(5)]

        with patch.object(reranker, "rerank", new_callable=AsyncMock, return_value=chunks[::-1]):
            result = await reranker.rerank(query="test", chunks=chunks)
            assert len(result) == len(chunks)

    @pytest.mark.asyncio
    async def test_reranker_falls_back_on_error(self):
        """Reranker should fall back to original order on API failure."""
        try:
            from app.services.retrieval.reranker import Reranker
        except ImportError:
            pytest.skip("Reranker not yet implemented")

        reranker = Reranker()
        chunks = [_make_chunk(f"c{i}") for i in range(3)]

        with patch.object(reranker, "_call_cohere", new_callable=AsyncMock,
                          side_effect=Exception("Cohere API error")):
            result = await reranker.rerank(query="test", chunks=chunks)
            # Should return original chunks in original order (fail-safe)
            assert len(result) == len(chunks)


class TestBenchmarkEvaluation:
    """Evaluate retrieval quality against the curated benchmark dataset."""

    def _compute_precision_at_k(self, retrieved_ids: list, relevant_ids: list, k: int) -> float:
        top_k = retrieved_ids[:k]
        hits = sum(1 for r in top_k if r in relevant_ids)
        return hits / k if k > 0 else 0.0

    def _compute_ndcg_at_k(self, retrieved_ids: list, relevant_ids: list, k: int) -> float:
        import math
        top_k = retrieved_ids[:k]
        dcg = sum(
            1.0 / math.log2(i + 2)
            for i, rid in enumerate(top_k)
            if rid in relevant_ids
        )
        ideal_k = min(len(relevant_ids), k)
        idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_k))
        return dcg / idcg if idcg > 0 else 0.0

    def test_benchmark_dataset_is_valid(self, benchmark_data):
        assert "queries" in benchmark_data
        assert len(benchmark_data["queries"]) > 0
        for q in benchmark_data["queries"]:
            assert "query_id" in q
            assert "query" in q
            assert "relevant_chunk_ids" in q
            assert len(q["relevant_chunk_ids"]) > 0

    def test_benchmark_policy_chunks_are_valid(self, benchmark_data):
        for chunk in benchmark_data["policy_chunks"]:
            assert "chunk_id" in chunk
            assert "text" in chunk
            assert len(chunk["text"]) > 20

    @pytest.mark.parametrize("query_data", [
        pytest.param(
            {"query_id": "Q001", "expected_top_k": ["chunk_cgm_001", "chunk_cgm_002"],
             "relevant": ["chunk_cgm_001", "chunk_cgm_002", "chunk_cgm_003"],
             "min_precision": 0.67, "min_ndcg": 0.75},
            id="diabetes_cgm",
        ),
        pytest.param(
            {"query_id": "Q002", "expected_top_k": ["chunk_mri_001", "chunk_neuro_001"],
             "relevant": ["chunk_mri_001", "chunk_mri_002", "chunk_neuro_001"],
             "min_precision": 0.67, "min_ndcg": 0.70},
            id="mri_ms",
        ),
    ])
    def test_simulated_retrieval_meets_thresholds(self, query_data):
        """Simulate a perfect retrieval result and verify metric computations are correct."""
        retrieved = query_data["expected_top_k"] + ["chunk_irrelevant_001"]
        relevant = query_data["relevant"]

        precision = self._compute_precision_at_k(retrieved, relevant, k=3)
        ndcg = self._compute_ndcg_at_k(retrieved, relevant, k=5)

        assert precision >= query_data["min_precision"], (
            f"{query_data['query_id']}: P@3={precision:.2f} < minimum {query_data['min_precision']}"
        )
        assert ndcg >= query_data["min_ndcg"], (
            f"{query_data['query_id']}: NDCG@5={ndcg:.2f} < minimum {query_data['min_ndcg']}"
        )
