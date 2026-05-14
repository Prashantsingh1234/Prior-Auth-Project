"""
Hybrid RAG retrieval package.

Orchestrates multi-strategy policy retrieval for the PA review workflow:

  - Semantic search       dense vector similarity via Pinecone
  - Hybrid search         dense + BM25 sparse via Pinecone native hybrid
  - CPT-aware retrieval   CPT code hierarchy expansion
  - ICD-aware retrieval   ICD-10 hierarchy expansion
  - RRF fusion            Reciprocal Rank Fusion across all strategies
  - Multi-signal scoring  vector_sim + code_match + temporal + payer
  - Reranking             Cohere reranker with score-fusion fallback
  - Evaluation            Precision@K, Recall@K, MRR, NDCG

Quick start:
    from app.services.retrieval import HybridRetrievalOrchestrator

    orchestrator = HybridRetrievalOrchestrator.from_settings()
    result = await orchestrator.retrieve(
        query="CGM coverage for type 2 diabetes",
        cpt_codes=["95249"],
        icd_codes=["E11.9"],
        top_k=5,
    )
    for policy in result.policies:
        print(policy.policy_id, policy.similarity_score)
"""

from app.services.retrieval.cpt_retriever import (
    CPTRetriever,
    CPTRetrievalResult,
    expand_cpt_codes,
)
from app.services.retrieval.evaluator import (
    RelevanceJudgements,
    RetrievalEvaluator,
    RetrievalMetrics,
)
from app.services.retrieval.fusion import (
    FusedMatch,
    RRFFusion,
    deduplicate_matches,
    normalize_scores,
    rrf_fuse,
    softmax_scores,
)
from app.services.retrieval.icd_retriever import (
    ICDRetriever,
    ICDRetrievalResult,
    expand_icd_codes,
    build_icd_query_terms,
)
from app.services.retrieval.orchestrator import (
    HybridRetrievalOrchestrator,
    OrchestratorConfig,
    OrchestratorResult,
)
from app.services.retrieval.reranker import (
    BaseReranker,
    CohereReranker,
    RerankerPipeline,
    ScoreFusionReranker,
)
from app.services.retrieval.scorer import (
    RelevanceScorer,
    ScoreBreakdown,
    ScorerConfig,
    score_matches,
)

__all__ = [
    # Primary interface
    "HybridRetrievalOrchestrator",
    "OrchestratorConfig",
    "OrchestratorResult",
    # Fusion
    "RRFFusion",
    "FusedMatch",
    "rrf_fuse",
    "normalize_scores",
    "softmax_scores",
    "deduplicate_matches",
    # Scoring
    "RelevanceScorer",
    "ScorerConfig",
    "ScoreBreakdown",
    "score_matches",
    # Reranking
    "RerankerPipeline",
    "CohereReranker",
    "ScoreFusionReranker",
    "BaseReranker",
    # CPT retrieval
    "CPTRetriever",
    "CPTRetrievalResult",
    "expand_cpt_codes",
    # ICD retrieval
    "ICDRetriever",
    "ICDRetrievalResult",
    "expand_icd_codes",
    "build_icd_query_terms",
    # Evaluation
    "RetrievalEvaluator",
    "RetrievalMetrics",
    "RelevanceJudgements",
]
