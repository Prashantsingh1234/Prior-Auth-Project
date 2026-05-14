"""
Retrieval evaluation metrics for the hybrid RAG pipeline.

Implements standard IR metrics:
  - Precision@K   — fraction of top-K results that are relevant
  - Recall@K      — fraction of all relevant docs found in top-K
  - MRR           — Mean Reciprocal Rank (position of first relevant result)
  - NDCG@K        — Normalized Discounted Cumulative Gain (ranking quality)
  - Hit@K         — binary: did any relevant doc appear in top-K?

Relevance judgements can be:
  - Binary:  {doc_id: 1 or 0}
  - Graded:  {doc_id: 0–3}  (for NDCG with gain levels)

Two usage modes:

1. Offline evaluation — given a ground-truth relevance dict, compute metrics
   against a retrieved match list (for batch benchmarking).

2. Online proxy evaluation — use code-overlap heuristics as a relevance proxy
   when no human judgements are available (for continuous production monitoring).

Usage:
    from app.services.retrieval.evaluator import RetrievalEvaluator, RelevanceJudgements

    # Offline (with ground truth)
    judgements = RelevanceJudgements({"policy-cpt95249-v1": 1, "policy-e11-v2": 1})
    metrics = RetrievalEvaluator.evaluate(matches, judgements, k=5)
    print(metrics.ndcg_at_k, metrics.mrr)

    # Online proxy (no ground truth)
    metrics = RetrievalEvaluator.evaluate_proxy(
        matches, k=5,
        query_cpt_codes=["95249"],
        query_icd_codes=["E11.9"],
    )
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.services.vector.schemas import RetrievalMatch

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Relevance judgements container
# ---------------------------------------------------------------------------

@dataclass
class RelevanceJudgements:
    """
    Maps policy_id (or vector_id) → relevance grade.

    Grade conventions:
      Binary:  0 = not relevant, 1 = relevant
      Graded:  0 = not relevant, 1 = marginally relevant,
               2 = relevant, 3 = highly relevant
    """
    grades: dict[str, int]

    def is_relevant(self, doc_id: str, threshold: int = 1) -> bool:
        return self.grades.get(doc_id, 0) >= threshold

    def grade(self, doc_id: str) -> int:
        return self.grades.get(doc_id, 0)

    @property
    def num_relevant(self) -> int:
        return sum(1 for g in self.grades.values() if g >= 1)


# ---------------------------------------------------------------------------
# Metrics result container
# ---------------------------------------------------------------------------

@dataclass
class RetrievalMetrics:
    """
    Computed retrieval evaluation metrics.

    All @K metrics are computed at the K specified in the evaluate() call.
    """
    k: int
    precision_at_k: float = 0.0
    recall_at_k:    float = 0.0
    mrr:            float = 0.0
    ndcg_at_k:      float = 0.0
    hit_at_k:       bool = False
    num_retrieved:  int = 0
    num_relevant:   int = 0
    num_relevant_retrieved: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "k":                      self.k,
            "precision_at_k":         round(self.precision_at_k, 4),
            "recall_at_k":            round(self.recall_at_k, 4),
            "mrr":                    round(self.mrr, 4),
            "ndcg_at_k":              round(self.ndcg_at_k, 4),
            "hit_at_k":               self.hit_at_k,
            "num_retrieved":          self.num_retrieved,
            "num_relevant":           self.num_relevant,
            "num_relevant_retrieved": self.num_relevant_retrieved,
        }

    def log(self, extra: dict | None = None) -> None:
        logger.info(
            "retrieval.evaluation",
            **(extra or {}),
            **self.to_dict(),
        )


# ---------------------------------------------------------------------------
# Core metric functions
# ---------------------------------------------------------------------------

def _precision_at_k(
    retrieved_ids: list[str],
    judgements: RelevanceJudgements,
    k: int,
) -> float:
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    relevant_in_k = sum(1 for doc_id in top_k if judgements.is_relevant(doc_id))
    return relevant_in_k / len(top_k)


def _recall_at_k(
    retrieved_ids: list[str],
    judgements: RelevanceJudgements,
    k: int,
) -> float:
    n_relevant = judgements.num_relevant
    if n_relevant == 0:
        return 0.0
    top_k = retrieved_ids[:k]
    relevant_in_k = sum(1 for doc_id in top_k if judgements.is_relevant(doc_id))
    return relevant_in_k / n_relevant


def _mrr(retrieved_ids: list[str], judgements: RelevanceJudgements) -> float:
    """
    Mean Reciprocal Rank — 1/rank of the first relevant document.

    Returns 0.0 if no relevant document is found.
    """
    for rank_0based, doc_id in enumerate(retrieved_ids):
        if judgements.is_relevant(doc_id):
            return 1.0 / (rank_0based + 1)
    return 0.0


def _dcg_at_k(
    retrieved_ids: list[str],
    judgements: RelevanceJudgements,
    k: int,
) -> float:
    """
    Discounted Cumulative Gain at K.

    Uses log base 2 discount: DCG@K = Σ gain_i / log2(i+1), i=1..K
    """
    dcg = 0.0
    for rank_0based, doc_id in enumerate(retrieved_ids[:k]):
        gain = judgements.grade(doc_id)
        discount = math.log2(rank_0based + 2)  # rank_0based+2 because i is 1-based
        dcg += gain / discount
    return dcg


def _ideal_dcg_at_k(judgements: RelevanceJudgements, k: int) -> float:
    """
    Ideal DCG: best possible DCG with this set of relevant documents.
    """
    sorted_grades = sorted(judgements.grades.values(), reverse=True)[:k]
    idcg = 0.0
    for rank_0based, gain in enumerate(sorted_grades):
        idcg += gain / math.log2(rank_0based + 2)
    return idcg


def _ndcg_at_k(
    retrieved_ids: list[str],
    judgements: RelevanceJudgements,
    k: int,
) -> float:
    """NDCG@K = DCG@K / IDCG@K."""
    idcg = _ideal_dcg_at_k(judgements, k)
    if idcg == 0.0:
        return 0.0
    return _dcg_at_k(retrieved_ids, judgements, k) / idcg


# ---------------------------------------------------------------------------
# Main evaluator class
# ---------------------------------------------------------------------------

class RetrievalEvaluator:
    """
    Compute retrieval quality metrics for a ranked result list.
    """

    @staticmethod
    def evaluate(
        matches: list[RetrievalMatch],
        judgements: RelevanceJudgements,
        k: int = 5,
        *,
        id_field: str = "policy_id",
    ) -> RetrievalMetrics:
        """
        Evaluate a retrieval result against ground-truth relevance judgements.

        Args:
            matches:    Ranked list of retrieved matches (descending score).
            judgements: Ground-truth relevance grades keyed by policy_id or vector_id.
            k:          Cutoff for @K metrics.
            id_field:   Which ID to look up: "policy_id" or "vector_id".

        Returns:
            RetrievalMetrics with all IR metrics filled.
        """
        def _get_id(m: RetrievalMatch) -> str:
            if id_field == "vector_id":
                return m.vector_id
            return m.metadata.policy_id

        retrieved_ids = [_get_id(m) for m in matches]
        top_k_ids = retrieved_ids[:k]

        relevant_in_k = sum(
            1 for doc_id in top_k_ids if judgements.is_relevant(doc_id)
        )

        prec = _precision_at_k(retrieved_ids, judgements, k)
        rec  = _recall_at_k(retrieved_ids, judgements, k)
        mrr  = _mrr(retrieved_ids, judgements)
        ndcg = _ndcg_at_k(retrieved_ids, judgements, k)
        hit  = any(judgements.is_relevant(doc_id) for doc_id in top_k_ids)

        return RetrievalMetrics(
            k=k,
            precision_at_k=prec,
            recall_at_k=rec,
            mrr=mrr,
            ndcg_at_k=ndcg,
            hit_at_k=hit,
            num_retrieved=len(matches),
            num_relevant=judgements.num_relevant,
            num_relevant_retrieved=relevant_in_k,
        )

    @staticmethod
    def evaluate_proxy(
        matches: list[RetrievalMatch],
        k: int = 5,
        *,
        query_cpt_codes: list[str] | None = None,
        query_icd_codes: list[str] | None = None,
        min_score_threshold: float = 0.70,
    ) -> RetrievalMetrics:
        """
        Proxy evaluation using code-overlap and score heuristics.

        Used in production when no human judgements are available.

        Relevance heuristic:
          A result is considered "relevant" if:
          - score >= min_score_threshold, OR
          - it shares at least one CPT or ICD code with the query

        This is an approximation — use offline evaluate() for benchmarking.
        """
        query_cpts = set(c.upper() for c in (query_cpt_codes or []))
        query_icds = set(c.upper() for c in (query_icd_codes or []))

        grades: dict[str, int] = {}
        for m in matches:
            policy_cpts = set(c.upper() for c in m.metadata.cpt_codes)
            policy_icds = set(c.upper() for c in m.metadata.icd_codes)

            has_code_overlap = bool(
                (query_cpts and query_cpts & policy_cpts)
                or (query_icds and query_icds & policy_icds)
            )
            high_score = m.score >= min_score_threshold

            if has_code_overlap and high_score:
                grades[m.metadata.policy_id] = 2
            elif has_code_overlap or high_score:
                grades[m.metadata.policy_id] = 1
            else:
                grades[m.metadata.policy_id] = 0

        judgements = RelevanceJudgements(grades=grades)
        return RetrievalEvaluator.evaluate(matches, judgements, k=k)

    @staticmethod
    def average_metrics(metrics_list: list[RetrievalMetrics]) -> RetrievalMetrics:
        """
        Compute mean metrics over a list of per-query results.

        Useful for batch benchmarking across multiple test queries.
        """
        if not metrics_list:
            return RetrievalMetrics(k=0)

        k = metrics_list[0].k
        n = len(metrics_list)
        return RetrievalMetrics(
            k=k,
            precision_at_k=sum(m.precision_at_k for m in metrics_list) / n,
            recall_at_k=sum(m.recall_at_k for m in metrics_list) / n,
            mrr=sum(m.mrr for m in metrics_list) / n,
            ndcg_at_k=sum(m.ndcg_at_k for m in metrics_list) / n,
            hit_at_k=sum(1 for m in metrics_list if m.hit_at_k) / n >= 0.5,
            num_retrieved=sum(m.num_retrieved for m in metrics_list) // n,
            num_relevant=sum(m.num_relevant for m in metrics_list) // n,
            num_relevant_retrieved=sum(m.num_relevant_retrieved for m in metrics_list) // n,
        )
