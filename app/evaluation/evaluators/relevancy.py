"""
Answer relevancy evaluator using RAGAS + DeepEval.

Relevancy measures how well the generated answer addresses the original
question.  An answer can be completely faithful to its context yet still
be irrelevant if the model answered a different question.

Sources:
  RAGAS answer_relevancy  — embeds the answer and question, measures cosine similarity
                            between the question and reverse-generated questions from the answer
  DeepEval AnswerRelevancyMetric — LLM-judge approach comparing answer to question

Both are run when available; the final score is their mean.

Score contract: 0.0–1.0, higher is better.
Threshold: 0.75.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import structlog

from app.evaluation.evaluators.base import BaseEvaluator, EvalInput
from app.evaluation.models import EvalMetric

logger = structlog.get_logger(__name__)

_THRESHOLD = 0.75
_WEIGHT    = 1.0


class AnswerRelevancyEvaluator(BaseEvaluator):
    """
    Combines RAGAS and DeepEval relevancy signals.

    Gracefully degrades to single-source scoring when one backend fails.
    Falls back to BM25-style keyword overlap in fully offline environments.
    """

    name = "answer_relevancy"

    async def evaluate(self, inp: EvalInput) -> list[EvalMetric]:
        if not inp.generated_output or not inp.query:
            return [EvalMetric(
                name="answer_relevancy",
                value=0.0,
                threshold=_THRESHOLD,
                weight=_WEIGHT,
                details={"skipped": "missing query or output"},
            )]

        ragas_score, deepeval_score = await asyncio.gather(
            self._ragas_relevancy(inp),
            self._deepeval_relevancy(inp),
        )

        valid = [s for s in [ragas_score, deepeval_score] if s is not None]
        if not valid:
            return [self._heuristic_fallback(inp)]

        combined = round(sum(valid) / len(valid), 4)
        return [EvalMetric(
            name="answer_relevancy",
            value=combined,
            threshold=_THRESHOLD,
            weight=_WEIGHT,
            details={
                "ragas_score":    round(ragas_score, 4) if ragas_score is not None else None,
                "deepeval_score": round(deepeval_score, 4) if deepeval_score is not None else None,
                "backend":        "ragas+deepeval" if len(valid) == 2 else "single_source",
            },
        )]

    async def _ragas_relevancy(self, inp: EvalInput) -> float | None:
        try:
            from ragas import evaluate as ragas_evaluate
            from ragas.metrics import answer_relevancy
            from datasets import Dataset

            if not os.getenv("OPENAI_API_KEY"):
                return None

            data: dict[str, list[Any]] = {
                "question": [inp.query],
                "contexts": [inp.context_docs or [""]],
                "answer":   [inp.generated_output],
            }
            dataset = Dataset.from_dict(data)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: ragas_evaluate(dataset, metrics=[answer_relevancy]),
            )
            return float(result["answer_relevancy"])
        except Exception as exc:
            logger.debug("relevancy.ragas_failed", error=str(exc))
            return None

    async def _deepeval_relevancy(self, inp: EvalInput) -> float | None:
        try:
            from deepeval.metrics import AnswerRelevancyMetric
            from deepeval.test_case import LLMTestCase

            test_case = LLMTestCase(
                input=inp.query,
                actual_output=inp.generated_output,
                expected_output=inp.expected_output,
            )
            metric = AnswerRelevancyMetric(threshold=_THRESHOLD)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, metric.measure, test_case)
            return float(metric.score or 0.0)
        except Exception as exc:
            logger.debug("relevancy.deepeval_failed", error=str(exc))
            return None

    @staticmethod
    def _heuristic_fallback(inp: EvalInput) -> EvalMetric:
        """Jaccard similarity between query tokens and output tokens."""
        q_tokens = set(inp.query.lower().split())
        a_tokens = set(inp.generated_output.lower().split())
        if not q_tokens or not a_tokens:
            score = 0.0
        else:
            score = len(q_tokens & a_tokens) / len(q_tokens | a_tokens)

        return EvalMetric(
            name="answer_relevancy",
            value=round(score, 4),
            threshold=_THRESHOLD,
            weight=_WEIGHT,
            details={"backend": "heuristic_fallback"},
        )
