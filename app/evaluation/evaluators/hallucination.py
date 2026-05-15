"""
Hallucination evaluator using DeepEval.

DeepEval's HallucinationMetric uses an LLM judge to check each factual
claim in the generated output against the provided context documents.
A claim is "hallucinated" when it cannot be grounded in any context chunk.

Score contract (after inversion):
  1.0 = fully grounded, no hallucinations detected
  0.0 = every claim is hallucinated

The inversion means higher is always better, consistent with all other
evaluators in this package.

Threshold: 0.75 (≤25% of claims may be unverifiable before triggering
a routing downgrade).  Healthcare contexts are stricter than general QA.
"""

from __future__ import annotations

import asyncio

import structlog

from app.evaluation.evaluators.base import BaseEvaluator, EvalInput
from app.evaluation.models import EvalMetric

logger = structlog.get_logger(__name__)

_THRESHOLD = 0.75
_WEIGHT    = 2.0   # hallucination is double-weighted in medical context


class HallucinationEvaluator(BaseEvaluator):
    """
    Detects hallucinated claims via DeepEval HallucinationMetric.

    Falls back to a heuristic length-based score when DeepEval is
    unavailable (CI, offline environments) so pipelines continue running.
    """

    name = "hallucination"

    async def evaluate(self, inp: EvalInput) -> list[EvalMetric]:
        if not inp.generated_output:
            return [EvalMetric(
                name="hallucination",
                value=1.0,           # no output = no hallucination
                threshold=_THRESHOLD,
                weight=_WEIGHT,
                details={"skipped": "empty output"},
            )]

        if not inp.context_docs:
            # Cannot evaluate hallucination without context — return neutral
            return [EvalMetric(
                name="hallucination",
                value=0.5,
                threshold=_THRESHOLD,
                weight=_WEIGHT,
                details={"skipped": "no context documents provided"},
            )]

        return await self._run_deepeval(inp)

    async def _run_deepeval(self, inp: EvalInput) -> list[EvalMetric]:
        try:
            from deepeval.metrics import HallucinationMetric
            from deepeval.test_case import LLMTestCase
        except ImportError:
            logger.warning("hallucination.deepeval_not_installed")
            return [self._heuristic_fallback(inp)]

        test_case = LLMTestCase(
            input=inp.query or "",
            actual_output=inp.generated_output,
            context=inp.context_docs,
        )
        # raw threshold: fraction of hallucinated claims that triggers failure
        raw_fail_threshold = 1.0 - _THRESHOLD
        metric = HallucinationMetric(threshold=raw_fail_threshold)

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, metric.measure, test_case)
        except Exception as exc:
            logger.error("hallucination.measure_failed", error=str(exc))
            return [self._heuristic_fallback(inp)]

        # DeepEval score: fraction of hallucinated claims (0=none, 1=all)
        raw: float = float(metric.score or 0.0)
        inverted = 1.0 - raw

        return [EvalMetric(
            name="hallucination",
            value=round(inverted, 4),
            threshold=_THRESHOLD,
            weight=_WEIGHT,
            details={
                "raw_hallucination_fraction": round(raw, 4),
                "reason": getattr(metric, "reason", ""),
                "backend": "deepeval",
            },
        )]

    @staticmethod
    def _heuristic_fallback(inp: EvalInput) -> EvalMetric:
        """
        Simple overlap heuristic when DeepEval is unavailable.

        Counts how many output tokens appear in at least one context doc.
        Not a substitute for a real LLM judge — used only in dev/CI.
        """
        output_tokens = set(inp.generated_output.lower().split())
        context_tokens = set(
            token
            for doc in inp.context_docs
            for token in doc.lower().split()
        )
        if not output_tokens:
            score = 1.0
        else:
            overlap = len(output_tokens & context_tokens) / len(output_tokens)
            score = round(overlap, 4)

        return EvalMetric(
            name="hallucination",
            value=score,
            threshold=_THRESHOLD,
            weight=_WEIGHT,
            details={"backend": "heuristic_fallback", "overlap_ratio": score},
        )
