"""
Retrieval quality evaluators using RAGAS.

Two metrics:
  context_precision — are the retrieved docs relevant to the question?
                      Penalizes retrieving irrelevant noise.
  context_recall    — does the retrieved context cover the ground truth?
                      Penalizes missing relevant information.

Both require a ground_truth_answer or ground_truth_docs to score against.

RAGAS definitions:
  context_precision = TP / (TP + FP) across retrieved chunks
  context_recall    = fraction of ground-truth statements supported
                      by at least one retrieved chunk

Score contract: 0.0–1.0, higher is better.
Thresholds: precision 0.70, recall 0.75.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import structlog

from app.evaluation.evaluators.base import BaseEvaluator, EvalInput
from app.evaluation.models import EvalMetric

logger = structlog.get_logger(__name__)

_PRECISION_THRESHOLD = 0.70
_RECALL_THRESHOLD    = 0.75
_WEIGHT              = 1.0


class RetrievalEvaluator(BaseEvaluator):
    """
    Context precision and recall via RAGAS.

    Both metrics are returned from a single evaluate() call to avoid
    running the RAGAS dataset evaluation twice.
    """

    name = "retrieval"

    async def evaluate(self, inp: EvalInput) -> list[EvalMetric]:
        if not inp.context_docs:
            return [
                EvalMetric(
                    name="retrieval.context_precision",
                    value=0.0,
                    threshold=_PRECISION_THRESHOLD,
                    weight=_WEIGHT,
                    details={"skipped": "no context docs"},
                ),
                EvalMetric(
                    name="retrieval.context_recall",
                    value=0.0,
                    threshold=_RECALL_THRESHOLD,
                    weight=_WEIGHT,
                    details={"skipped": "no context docs"},
                ),
            ]

        has_ground_truth = bool(
            inp.ground_truth_answer or inp.ground_truth_docs
        )
        if not has_ground_truth:
            return await self._precision_only(inp)

        return await self._run_ragas(inp)

    async def _run_ragas(self, inp: EvalInput) -> list[EvalMetric]:
        try:
            from ragas import evaluate as ragas_evaluate
            from ragas.metrics import context_precision, context_recall
            from datasets import Dataset
        except ImportError:
            logger.warning("retrieval.ragas_not_installed")
            return self._heuristic_fallback(inp)

        if not os.getenv("OPENAI_API_KEY"):
            logger.warning("retrieval.no_openai_key")
            return self._heuristic_fallback(inp)

        ground_truth = inp.ground_truth_answer or " ".join(inp.ground_truth_docs)
        data: dict[str, list[Any]] = {
            "question":     [inp.query or ""],
            "contexts":     [inp.context_docs],
            "answer":       [inp.generated_output or ""],
            "ground_truth": [ground_truth],
        }
        dataset = Dataset.from_dict(data)

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: ragas_evaluate(
                    dataset,
                    metrics=[context_precision, context_recall],
                ),
            )
            precision = float(result["context_precision"])
            recall    = float(result["context_recall"])
        except Exception as exc:
            logger.error("retrieval.ragas_failed", error=str(exc))
            return self._heuristic_fallback(inp)

        return [
            EvalMetric(
                name="retrieval.context_precision",
                value=round(precision, 4),
                threshold=_PRECISION_THRESHOLD,
                weight=_WEIGHT,
                details={"backend": "ragas"},
            ),
            EvalMetric(
                name="retrieval.context_recall",
                value=round(recall, 4),
                threshold=_RECALL_THRESHOLD,
                weight=_WEIGHT,
                details={"backend": "ragas"},
            ),
        ]

    async def _precision_only(self, inp: EvalInput) -> list[EvalMetric]:
        """
        When no ground truth is available, estimate precision via
        query-context token overlap (a poor proxy, but better than 0).
        """
        query_tokens = set(inp.query.lower().split()) if inp.query else set()
        if not query_tokens:
            score = 0.5
        else:
            scores = []
            for doc in inp.context_docs:
                doc_tokens = set(doc.lower().split())
                if doc_tokens:
                    overlap = len(query_tokens & doc_tokens) / len(query_tokens)
                    scores.append(overlap)
            score = sum(scores) / len(scores) if scores else 0.0

        return [
            EvalMetric(
                name="retrieval.context_precision",
                value=round(score, 4),
                threshold=_PRECISION_THRESHOLD,
                weight=_WEIGHT,
                details={"backend": "heuristic_no_ground_truth"},
            ),
            EvalMetric(
                name="retrieval.context_recall",
                value=0.0,
                threshold=_RECALL_THRESHOLD,
                weight=0.0,   # zero weight: unscored because no ground truth
                details={"skipped": "no ground_truth_answer or ground_truth_docs"},
            ),
        ]

    @staticmethod
    def _heuristic_fallback(inp: EvalInput) -> list[EvalMetric]:
        """
        Token-overlap heuristic for both precision and recall when
        RAGAS is unavailable.
        """
        query_tokens = set(inp.query.lower().split()) if inp.query else set()
        gt_tokens = (
            set(inp.ground_truth_answer.lower().split())
            if inp.ground_truth_answer
            else set(t for d in inp.ground_truth_docs for t in d.lower().split())
        )

        # Precision: fraction of query terms in retrieved context
        ctx_tokens = set(t for d in inp.context_docs for t in d.lower().split())
        precision = (
            len(query_tokens & ctx_tokens) / len(query_tokens)
            if query_tokens else 0.5
        )
        # Recall: fraction of GT terms covered by context
        recall = (
            len(gt_tokens & ctx_tokens) / len(gt_tokens)
            if gt_tokens else 0.5
        )

        return [
            EvalMetric(
                name="retrieval.context_precision",
                value=round(precision, 4),
                threshold=_PRECISION_THRESHOLD,
                weight=_WEIGHT,
                details={"backend": "heuristic_fallback"},
            ),
            EvalMetric(
                name="retrieval.context_recall",
                value=round(recall, 4),
                threshold=_RECALL_THRESHOLD,
                weight=_WEIGHT,
                details={"backend": "heuristic_fallback"},
            ),
        ]
