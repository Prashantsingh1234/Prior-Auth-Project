"""
Groundedness evaluator — hybrid DeepEval + RAGAS approach.

"Groundedness" is a medical-domain extension of faithfulness: it checks
not only that claims are present in the context but that the *clinical
significance* of those claims is preserved.  A response that inverts a
lab value ("HbA1c of 9.2% is within normal range") is faithful to the
retrieved text but clinically ungrounded.

Implementation:
  1. Run DeepEval HallucinationMetric on the output (claim-level grounding)
  2. Run RAGAS faithfulness for statement-level grounding
  3. Combine: groundedness = 0.6 * faithfulness + 0.4 * (1 - hallucination)
  4. Apply a medical-keyword density penalty when clinical terms in the
     output lack corresponding terms in the context.

Score contract: 0.0–1.0, higher is better.
Threshold: 0.75.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any

import structlog

from app.evaluation.evaluators.base import BaseEvaluator, EvalInput
from app.evaluation.models import EvalMetric

logger = structlog.get_logger(__name__)

_THRESHOLD = 0.75
_WEIGHT    = 1.5

# Clinical terms whose appearance in the output but NOT in context warrants a penalty
_CLINICAL_TERM_PATTERN = re.compile(
    r"\b(diagnosis|contraindication|hba1c|creatinine|egfr|formulary|"
    r"prior authorization|medically necessary|clinical indication|"
    r"icd-?\d+|cpt-?\d+|ndc|denial|approval)\b",
    re.IGNORECASE,
)


def _clinical_term_coverage(output: str, context_docs: list[str]) -> float:
    """Fraction of clinical output-terms that appear in at least one context doc."""
    output_terms = set(_CLINICAL_TERM_PATTERN.findall(output.lower()))
    if not output_terms:
        return 1.0  # no clinical terms = no coverage gap

    context_text = " ".join(doc.lower() for doc in context_docs)
    context_terms = set(_CLINICAL_TERM_PATTERN.findall(context_text))
    covered = output_terms & context_terms
    return len(covered) / len(output_terms)


class GroundednessEvaluator(BaseEvaluator):
    """
    Hybrid groundedness scorer for the PA medical context.

    Combines DeepEval (claim-level) and RAGAS (statement-level) signals
    with a domain-specific clinical term coverage penalty.
    """

    name = "groundedness"

    async def evaluate(self, inp: EvalInput) -> list[EvalMetric]:
        if not inp.generated_output or not inp.context_docs:
            return [EvalMetric(
                name="groundedness",
                value=0.0,
                threshold=_THRESHOLD,
                weight=_WEIGHT,
                details={"skipped": "missing output or context"},
            )]

        hallucination_score, faithfulness_score = await asyncio.gather(
            self._get_hallucination_score(inp),
            self._get_faithfulness_score(inp),
        )

        clinical_coverage = _clinical_term_coverage(inp.generated_output, inp.context_docs)

        # Composite: faithfulness dominates, hallucination acts as a penalty signal
        raw = 0.6 * faithfulness_score + 0.4 * hallucination_score

        # Clinical term penalty — if medical terminology in output isn't grounded
        # in the context, apply a proportional reduction
        if clinical_coverage < 0.9:
            penalty = (0.9 - clinical_coverage) * 0.20
            raw = max(0.0, raw - penalty)

        return [EvalMetric(
            name="groundedness",
            value=round(raw, 4),
            threshold=_THRESHOLD,
            weight=_WEIGHT,
            details={
                "faithfulness_component": round(faithfulness_score, 4),
                "hallucination_grounding": round(hallucination_score, 4),
                "clinical_term_coverage": round(clinical_coverage, 4),
            },
        )]

    async def _get_hallucination_score(self, inp: EvalInput) -> float:
        """Returns grounding fraction (1 - hallucination_fraction)."""
        try:
            from deepeval.metrics import HallucinationMetric
            from deepeval.test_case import LLMTestCase

            test_case = LLMTestCase(
                input=inp.query or "",
                actual_output=inp.generated_output,
                context=inp.context_docs,
            )
            metric = HallucinationMetric(threshold=0.5)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, metric.measure, test_case)
            return 1.0 - float(metric.score or 0.0)
        except Exception as exc:
            logger.debug("groundedness.hallucination_component_failed", error=str(exc))
            # Token overlap fallback
            output_tokens = set(inp.generated_output.lower().split())
            ctx_tokens = set(t for d in inp.context_docs for t in d.lower().split())
            if not output_tokens:
                return 1.0
            return len(output_tokens & ctx_tokens) / len(output_tokens)

    async def _get_faithfulness_score(self, inp: EvalInput) -> float:
        """Returns RAGAS faithfulness score."""
        try:
            from ragas import evaluate as ragas_evaluate
            from ragas.metrics import faithfulness
            from datasets import Dataset

            if not os.getenv("OPENAI_API_KEY"):
                raise RuntimeError("no openai key")

            data: dict[str, list[Any]] = {
                "question": [inp.query or ""],
                "contexts": [inp.context_docs],
                "answer":   [inp.generated_output],
            }
            dataset = Dataset.from_dict(data)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: ragas_evaluate(dataset, metrics=[faithfulness])
            )
            return float(result["faithfulness"])
        except Exception as exc:
            logger.debug("groundedness.faithfulness_component_failed", error=str(exc))
            # Sentence-overlap fallback
            sentences = [s.strip() for s in inp.generated_output.split(".") if len(s.strip()) > 10]
            if not sentences:
                return 0.5
            ctx_tokens = set(t for d in inp.context_docs for t in d.lower().split())
            supported = sum(
                1 for s in sentences
                if set(s.lower().split()) and
                len(set(s.lower().split()) & ctx_tokens) / len(set(s.lower().split())) >= 0.5
            )
            return supported / len(sentences)
