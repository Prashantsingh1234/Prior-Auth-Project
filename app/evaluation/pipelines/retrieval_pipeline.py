"""
Policy retrieval evaluation pipeline.

Evaluates the retrieval stage (vector search / hybrid search):
  - Context precision: are the returned policies relevant to the query?
  - Context recall:    are the ground-truth policies in the retrieved set?
  - Answer relevancy:  does the synthesised retrieval answer address the query?

The pipeline queries the policy retrieval service and measures how well
the retrieved chunks match the expected ground-truth policies.
"""

from __future__ import annotations

import json
import time

import structlog

from app.evaluation.evaluators.base import EvalInput
from app.evaluation.models import (
    BenchmarkCase,
    EvalDomain,
    EvalMetric,
    ModelEvalResult,
    ModelTier,
    TokenUsage,
)
from app.evaluation.pipelines.base import EvaluationPipeline

logger = structlog.get_logger(__name__)


class RetrievalEvaluationPipeline(EvaluationPipeline):
    """
    Evaluates the policy retrieval service.

    For each benchmark case it:
      1. Calls the retrieval service with case.query
      2. Collects returned policy chunks
      3. Runs RAGAS context_precision + context_recall
      4. Computes a recall@k metric against ground_truth_policies
    """

    domain = EvalDomain.RETRIEVAL

    async def run_case(
        self,
        case: BenchmarkCase,
        model_id: str,
        model_tier: ModelTier,
        run_id: str,
    ) -> ModelEvalResult:
        t0 = time.monotonic()
        retrieved_docs: list[str] = []
        synthesised_answer = ""
        token_usage = TokenUsage()
        error: str | None = None

        query = case.query or case.input_text[:300]

        try:
            retrieved_docs, synthesised_answer, token_usage = await self._call_retrieval(
                query, model_id
            )
        except Exception as exc:
            error = str(exc)
            logger.error("retrieval_pipeline.service_failed", error=error)

        latency_ms = (time.monotonic() - t0) * 1000

        eval_input = EvalInput(
            query=query,
            context_docs=retrieved_docs,
            generated_output=synthesised_answer,
            ground_truth_docs=case.ground_truth_policies,
            ground_truth_answer=case.ground_truth_answer,
            metadata={"case_id": case.case_id},
        )

        evaluator = self._make_evaluator(run_id)
        result = await evaluator.evaluate(
            inp=eval_input,
            model_id=model_id,
            model_tier=model_tier,
            case_id=case.case_id,
            token_usage=token_usage,
            latency_ms=latency_ms,
        )

        # Recall@k: fraction of ground-truth policies found in top-k retrieved
        if case.ground_truth_policies and retrieved_docs:
            recall_at_k = _recall_at_k(case.ground_truth_policies, retrieved_docs)
            result.add_metric(EvalMetric(
                name="retrieval.recall_at_k",
                value=round(recall_at_k, 4),
                threshold=0.70,
                weight=1.2,
                details={"k": len(retrieved_docs)},
            ))

        if error:
            result.error = error

        return result

    async def _call_retrieval(
        self,
        query: str,
        model_id: str,
    ) -> tuple[list[str], str, TokenUsage]:
        """
        Call the policy retrieval service.

        Returns (retrieved_doc_texts, synthesised_answer, token_usage).
        """
        try:
            from app.services.retrieval.service import get_retrieval_service

            service = get_retrieval_service()
            result  = await service.retrieve(query=query)
            docs    = [
                getattr(p, "content", str(p))
                for p in getattr(result, "policies", [])
            ]
            answer  = getattr(result, "answer", "") or ""
            tokens  = TokenUsage(prompt_tokens=getattr(result, "tokens_used", 0))
            return docs, answer, tokens
        except ImportError:
            logger.debug("retrieval_pipeline.service_stub")
            return _stub_retrieval(query), "", TokenUsage(prompt_tokens=200)

    @staticmethod
    def _ls_tags() -> list[str]:
        return ["retrieval", "evaluation"]


def _recall_at_k(ground_truth: list[str], retrieved: list[str]) -> float:
    """
    Fraction of ground-truth policies referenced in retrieved docs.
    Uses substring matching (policy IDs / policy names).
    """
    if not ground_truth:
        return 1.0
    combined_retrieved = " ".join(retrieved).lower()
    found = sum(
        1 for gt in ground_truth
        if gt.lower() in combined_retrieved
    )
    return found / len(ground_truth)


def _stub_retrieval(query: str) -> list[str]:
    return [
        f"[Stub] Policy document relevant to: {query[:100]}",
        "[Stub] General prior authorization coverage criteria.",
    ]
