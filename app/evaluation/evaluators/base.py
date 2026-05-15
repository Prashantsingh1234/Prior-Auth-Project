"""
Abstract base evaluator interface.

All evaluators in this package implement BaseEvaluator.  The contract:

  - evaluate() is async (sync SDKs run in an executor)
  - evaluate() never raises — errors return a low-score EvalMetric
  - evaluate() returns at least one EvalMetric
  - Implementations are stateless and concurrency-safe

EvalInput is the universal input envelope.  Fields are optional so each
evaluator can pick what it needs; unused fields are ignored.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.evaluation.models import EvalMetric

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Input envelope
# ---------------------------------------------------------------------------

@dataclass
class EvalInput:
    """
    Universal input envelope for all evaluators.

    Populate only the fields needed by the specific evaluator(s) you're
    invoking; unused fields are ignored without error.
    """
    # What the user / system asked
    query: str = ""

    # Context documents retrieved for the query (used by faithfulness,
    # groundedness, retrieval, hallucination evaluators)
    context_docs: list[str] = field(default_factory=list)

    # The LLM's generated response
    generated_output: str = ""

    # Gold-standard expected answer (used by relevancy, decision evaluators)
    expected_output: str | None = None

    # Ground-truth supporting documents (used by retrieval recall)
    ground_truth_docs: list[str] = field(default_factory=list)

    # Ground-truth answer string (used by RAGAS answer_correctness)
    ground_truth_answer: str | None = None

    # Structured ground-truth for decision accuracy
    expected_verdict: str | None = None        # "APPROVE" / "DENY" / "PEND"
    actual_verdict:   str | None = None

    # Human reviewer decision (used by reviewer_agreement evaluator)
    reviewer_verdict: str | None = None
    reviewer_id:      str | None = None

    # Conversation history for multi-turn evals
    chat_history: list[dict[str, str]] = field(default_factory=list)

    # Free-form pass-through for evaluator-specific data
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseEvaluator(ABC):
    """
    Abstract base for all evaluators.

    Subclasses must:
      - Set `name` as a class attribute (used in metric names and logs)
      - Implement `evaluate(inp: EvalInput) -> list[EvalMetric]`

    Use `evaluate_safe()` instead of `evaluate()` in production code —
    it guarantees a metric is always returned even if the evaluator crashes.
    """

    name: str = "base"

    @abstractmethod
    async def evaluate(self, inp: EvalInput) -> list[EvalMetric]:
        """Run the evaluation and return scored metrics."""

    async def evaluate_safe(self, inp: EvalInput) -> list[EvalMetric]:
        """
        Wraps evaluate() with error capture.

        Returns an error metric on failure rather than propagating the
        exception — critical for the composite evaluator that must
        complete even when individual evaluators fail.
        """
        try:
            metrics = await self.evaluate(inp)
            if not metrics:
                # Guard: evaluators must return at least one metric
                logger.warning("evaluator.empty_result", evaluator=self.name)
                return [EvalMetric(
                    name=f"{self.name}.empty",
                    value=0.0,
                    threshold=0.5,
                    details={"warning": "evaluator returned no metrics"},
                )]
            return metrics
        except Exception as exc:
            logger.error(
                "evaluator.error",
                evaluator=self.name,
                error=str(exc),
                exc_info=True,
            )
            return [EvalMetric(
                name=f"{self.name}.error",
                value=0.0,
                threshold=0.5,
                details={"error": str(exc), "evaluator": self.name},
            )]
