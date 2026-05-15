"""
End-to-end evaluation pipeline.

Runs the full PA workflow (extraction → retrieval → reasoning → decision)
and evaluates all stages in a single pass.

Metrics produced combine all domain metrics:
  Extraction:  hallucination, faithfulness, entity_coverage
  Retrieval:   context_precision, context_recall, recall@k
  Reasoning:   decision accuracy, reviewer agreement, groundedness
  System:      total latency, total tokens, total cost, json_validation

Use this pipeline for:
  - Full system benchmarking
  - Regression testing before deployments
  - Model comparison across the full pipeline

Design note: each stage runs its own LangSmith trace so individual
stage failures are visible in the LangSmith UI without obscuring E2E runs.
"""

from __future__ import annotations

import time

import structlog

from app.evaluation.evaluators.base import EvalInput
from app.evaluation.evaluators.composite import CompositeEvaluator
from app.evaluation.models import (
    BenchmarkCase,
    EvalDomain,
    EvalMetric,
    ModelEvalResult,
    ModelTier,
    TokenUsage,
)
from app.evaluation.pipelines.base import EvaluationPipeline
from app.evaluation.pipelines.extraction_pipeline import (
    ExtractionEvaluationPipeline,
    _compute_entity_coverage,
    _entities_to_text,
)
from app.evaluation.pipelines.retrieval_pipeline import (
    RetrievalEvaluationPipeline,
    _recall_at_k,
)
from app.evaluation.pipelines.reasoning_pipeline import (
    ReasoningEvaluationPipeline,
    _stub_reasoning_output,
)

logger = structlog.get_logger(__name__)


class EndToEndEvaluationPipeline(EvaluationPipeline):
    """
    Evaluates the complete PA workflow for a single case.

    Runs extraction → retrieval → reasoning in sequence.
    Each stage's output feeds the next stage's input.
    All metrics from all stages are merged into one ModelEvalResult.
    """

    domain = EvalDomain.END_TO_END

    def __init__(self, langsmith_client=None) -> None:
        super().__init__(langsmith_client)
        self._extraction = ExtractionEvaluationPipeline(langsmith_client)
        self._retrieval  = RetrievalEvaluationPipeline(langsmith_client)
        self._reasoning  = ReasoningEvaluationPipeline(langsmith_client)

    async def run_case(
        self,
        case: BenchmarkCase,
        model_id: str,
        model_tier: ModelTier,
        run_id: str,
    ) -> ModelEvalResult:
        t_start = time.monotonic()
        total_tokens = TokenUsage()

        # ----------------------------------------------------------------
        # Stage 1: Extraction
        # ----------------------------------------------------------------
        t0 = time.monotonic()
        extracted_json = ""
        try:
            extracted_json, ext_tokens = await self._extraction._call_extraction(
                case.input_text, model_id
            )
            total_tokens.prompt_tokens     += ext_tokens.prompt_tokens
            total_tokens.completion_tokens += ext_tokens.completion_tokens
        except Exception as exc:
            logger.warning("e2e.extraction_failed", error=str(exc))
        extraction_ms = (time.monotonic() - t0) * 1000

        # ----------------------------------------------------------------
        # Stage 2: Retrieval
        # ----------------------------------------------------------------
        t0 = time.monotonic()
        retrieved_docs: list[str] = case.context_docs.copy()
        synthesised_answer = ""
        try:
            query = case.query or case.input_text[:200]
            ret_docs, synthesised_answer, ret_tokens = await self._retrieval._call_retrieval(
                query, model_id
            )
            if ret_docs:
                retrieved_docs = ret_docs
            total_tokens.prompt_tokens     += ret_tokens.prompt_tokens
            total_tokens.completion_tokens += ret_tokens.completion_tokens
        except Exception as exc:
            logger.warning("e2e.retrieval_failed", error=str(exc))
        retrieval_ms = (time.monotonic() - t0) * 1000

        # ----------------------------------------------------------------
        # Stage 3: Reasoning
        # ----------------------------------------------------------------
        t0 = time.monotonic()
        rationale = ""
        verdict   = ""
        # Build a temporary case with the retrieved context
        enriched_case = case.model_copy(update={"context_docs": retrieved_docs})
        try:
            rationale, verdict, rsn_tokens = await self._reasoning._call_reasoning(
                enriched_case, model_id
            )
            total_tokens.prompt_tokens     += rsn_tokens.prompt_tokens
            total_tokens.completion_tokens += rsn_tokens.completion_tokens
        except Exception as exc:
            logger.warning("e2e.reasoning_failed", error=str(exc))
        reasoning_ms = (time.monotonic() - t0) * 1000

        total_ms = (time.monotonic() - t_start) * 1000

        # ----------------------------------------------------------------
        # Evaluate full output
        # ----------------------------------------------------------------
        combined_output = rationale or extracted_json or ""
        eval_input = EvalInput(
            query=case.query or "Evaluate this prior authorization request.",
            context_docs=retrieved_docs,
            generated_output=combined_output,
            expected_output=case.ground_truth_answer or case.expected_verdict,
            expected_verdict=case.expected_verdict,
            actual_verdict=verdict or None,
            reviewer_verdict=case.metadata.get("reviewer_verdict"),
            ground_truth_docs=case.ground_truth_policies,
            ground_truth_answer=case.ground_truth_answer,
            metadata={"case_id": case.case_id, "model_id": model_id, "stage": "e2e"},
        )

        evaluator = self._make_evaluator(run_id)
        result = await evaluator.evaluate(
            inp=eval_input,
            model_id=model_id,
            model_tier=model_tier,
            case_id=case.case_id,
            token_usage=total_tokens,
            latency_ms=total_ms,
        )

        # ----------------------------------------------------------------
        # Stage timing metrics
        # ----------------------------------------------------------------
        result.add_metric(EvalMetric(
            name="e2e.extraction_latency_ms",
            value=min(1.0, 1.0 - extraction_ms / 30_000),   # normalised: 30s = score 0
            threshold=0.5,
            weight=0.3,
            details={"extraction_ms": round(extraction_ms, 1)},
        ))
        result.add_metric(EvalMetric(
            name="e2e.retrieval_latency_ms",
            value=min(1.0, 1.0 - retrieval_ms / 10_000),
            threshold=0.5,
            weight=0.3,
            details={"retrieval_ms": round(retrieval_ms, 1)},
        ))
        result.add_metric(EvalMetric(
            name="e2e.reasoning_latency_ms",
            value=min(1.0, 1.0 - reasoning_ms / 60_000),
            threshold=0.5,
            weight=0.3,
            details={"reasoning_ms": round(reasoning_ms, 1)},
        ))

        # Entity coverage
        if case.expected_entities and extracted_json:
            coverage = _compute_entity_coverage(extracted_json, case.expected_entities)
            result.add_metric(EvalMetric(
                name="extraction.entity_coverage",
                value=round(coverage, 4),
                threshold=0.80,
                weight=1.2,
            ))

        # Retrieval recall@k
        if case.ground_truth_policies and retrieved_docs:
            result.add_metric(EvalMetric(
                name="retrieval.recall_at_k",
                value=round(_recall_at_k(case.ground_truth_policies, retrieved_docs), 4),
                threshold=0.70,
                weight=1.0,
            ))

        return result
