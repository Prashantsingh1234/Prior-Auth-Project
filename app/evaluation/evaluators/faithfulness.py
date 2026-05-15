"""
Faithfulness evaluator using RAGAS.

RAGAS faithfulness measures whether all claims in the generated answer
can be inferred from the provided context.  Unlike hallucination (which
is claim-level), faithfulness is answer-level: the score is the fraction
of answer statements that are supported by the context.

Score contract: 0.0–1.0, higher is better.
Threshold: 0.80 — at least 80% of answer statements must be context-backed.

RAGAS requires an LLM backend (defaults to GPT-4o-mini via OpenAI).  The
OpenAI API key is read from the OPENAI_API_KEY environment variable.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import structlog

from app.evaluation.evaluators.base import BaseEvaluator, EvalInput
from app.evaluation.models import EvalMetric

logger = structlog.get_logger(__name__)

_THRESHOLD = 0.80
_WEIGHT    = 1.5


class FaithfulnessEvaluator(BaseEvaluator):
    """
    Faithfulness scorer via RAGAS.

    Falls back to a precision-based heuristic when RAGAS / the OpenAI
    key are unavailable so CI pipelines continue unblocked.
    """

    name = "faithfulness"

    async def evaluate(self, inp: EvalInput) -> list[EvalMetric]:
        if not inp.generated_output or not inp.context_docs:
            return [EvalMetric(
                name="faithfulness",
                value=0.0,
                threshold=_THRESHOLD,
                weight=_WEIGHT,
                details={"skipped": "missing output or context"},
            )]

        return await self._run_ragas(inp)

    async def _run_ragas(self, inp: EvalInput) -> list[EvalMetric]:
        try:
            from ragas import evaluate as ragas_evaluate
            from ragas.metrics import faithfulness
            from datasets import Dataset
        except ImportError:
            logger.warning("faithfulness.ragas_not_installed")
            return [self._heuristic_fallback(inp)]

        if not os.getenv("OPENAI_API_KEY"):
            logger.warning("faithfulness.no_openai_key")
            return [self._heuristic_fallback(inp)]

        data: dict[str, list[Any]] = {
            "question":  [inp.query or ""],
            "contexts":  [inp.context_docs],
            "answer":    [inp.generated_output],
        }
        if inp.ground_truth_answer:
            data["ground_truth"] = [inp.ground_truth_answer]

        dataset = Dataset.from_dict(data)

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: ragas_evaluate(dataset, metrics=[faithfulness]),
            )
            score: float = float(result["faithfulness"])
        except Exception as exc:
            logger.error("faithfulness.ragas_failed", error=str(exc))
            return [self._heuristic_fallback(inp)]

        return [EvalMetric(
            name="faithfulness",
            value=round(score, 4),
            threshold=_THRESHOLD,
            weight=_WEIGHT,
            details={"backend": "ragas"},
        )]

    @staticmethod
    def _heuristic_fallback(inp: EvalInput) -> EvalMetric:
        """
        Sentence-level precision proxy: fraction of output sentences
        that share ≥50% token overlap with any context sentence.
        """
        output_sentences = [
            s.strip() for s in inp.generated_output.split(".")
            if len(s.strip()) > 10
        ]
        if not output_sentences:
            return EvalMetric(
                name="faithfulness",
                value=0.5,
                threshold=_THRESHOLD,
                weight=_WEIGHT,
                details={"backend": "heuristic_fallback"},
            )

        context_text = " ".join(inp.context_docs).lower()
        context_tokens = set(context_text.split())
        supported = 0

        for sentence in output_sentences:
            s_tokens = set(sentence.lower().split())
            if s_tokens and len(s_tokens & context_tokens) / len(s_tokens) >= 0.5:
                supported += 1

        score = round(supported / len(output_sentences), 4)
        return EvalMetric(
            name="faithfulness",
            value=score,
            threshold=_THRESHOLD,
            weight=_WEIGHT,
            details={
                "backend": "heuristic_fallback",
                "supported_sentences": supported,
                "total_sentences": len(output_sentences),
            },
        )
