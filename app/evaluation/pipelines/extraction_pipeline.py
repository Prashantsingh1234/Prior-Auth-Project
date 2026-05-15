"""
Medical entity extraction evaluation pipeline.

Evaluates the quality of the extraction stage (OCR → entity extraction):
  - Hallucination: are extracted entities supported by the source text?
  - Faithfulness:  are extracted entities present in the source text?
  - Groundedness:  are clinical terms correctly extracted?
  - Extraction accuracy: entity counts + field coverage vs ground truth

The pipeline calls app.services.extraction.service (when available) to
get real extraction output.  Falls back to synthetic output in test mode.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from app.evaluation.evaluators.base import EvalInput
from app.evaluation.models import (
    BenchmarkCase,
    EvalDomain,
    ModelEvalResult,
    ModelTier,
    TokenUsage,
)
from app.evaluation.pipelines.base import EvaluationPipeline

logger = structlog.get_logger(__name__)


class ExtractionEvaluationPipeline(EvaluationPipeline):
    """
    Evaluates the medical entity extraction service.

    For each benchmark case it:
      1. Calls the extraction service with the case's input_text
      2. Serialises the extraction output to a JSON string
      3. Measures entity coverage vs expected_entities
      4. Runs the evaluator suite (hallucination, faithfulness, groundedness)
    """

    domain = EvalDomain.EXTRACTION

    async def run_case(
        self,
        case: BenchmarkCase,
        model_id: str,
        model_tier: ModelTier,
        run_id: str,
    ) -> ModelEvalResult:
        t0 = time.monotonic()
        generated_output = ""
        token_usage      = TokenUsage()
        error: str | None = None

        # --- Call extraction service ---
        try:
            generated_output, token_usage = await self._call_extraction(
                case.input_text, model_id
            )
        except Exception as exc:
            error = str(exc)
            logger.error("extraction_pipeline.service_failed", error=error)
            generated_output = ""

        latency_ms = (time.monotonic() - t0) * 1000

        # --- Build EvalInput ---
        eval_input = EvalInput(
            query=case.query or "Extract medical entities from the clinical text.",
            context_docs=[case.input_text],   # source text acts as context
            generated_output=generated_output,
            expected_output=_entities_to_text(case.expected_entities),
            ground_truth_answer=_entities_to_text(case.expected_entities),
            metadata={"case_id": case.case_id, "model_id": model_id},
        )

        # --- Score ---
        evaluator = self._make_evaluator(run_id)
        result = await evaluator.evaluate(
            inp=eval_input,
            model_id=model_id,
            model_tier=model_tier,
            case_id=case.case_id,
            token_usage=token_usage,
            latency_ms=latency_ms,
        )

        # --- Entity coverage metric ---
        if case.expected_entities and generated_output:
            coverage = _compute_entity_coverage(generated_output, case.expected_entities)
            from app.evaluation.models import EvalMetric
            result.add_metric(EvalMetric(
                name="extraction.entity_coverage",
                value=round(coverage, 4),
                threshold=0.80,
                weight=1.5,
                details={"expected_entity_types": list(case.expected_entities.keys())},
            ))

        if error:
            result.error = error

        return result

    async def _call_extraction(
        self,
        text: str,
        model_id: str,
    ) -> tuple[str, TokenUsage]:
        """
        Call the real extraction service.

        Returns (serialised_output_json, token_usage).
        Raises on hard failures so the pipeline can record the error.
        """
        try:
            from app.services.extraction.service import get_extraction_service
            import json as _json

            service = get_extraction_service()
            result  = await service.extract(text=text, model_override=model_id)
            output  = _json.dumps(result.model_dump() if hasattr(result, "model_dump") else result)
            tokens  = TokenUsage(
                prompt_tokens=getattr(result, "llm_tokens_used", 0),
            )
            return output, tokens
        except ImportError:
            # Service not yet wired up — return a stub response for evaluation
            return _stub_extraction_output(text), TokenUsage(prompt_tokens=500)

    @staticmethod
    def _ls_tags() -> list[str]:
        return ["extraction", "evaluation"]


def _entities_to_text(entities: dict) -> str:
    """Flatten entity dict to a readable string for evaluators."""
    if not entities:
        return ""
    parts = []
    for entity_type, values in entities.items():
        if isinstance(values, list):
            parts.append(f"{entity_type}: {', '.join(str(v) for v in values)}")
        else:
            parts.append(f"{entity_type}: {values}")
    return ". ".join(parts)


def _compute_entity_coverage(output: str, expected: dict) -> float:
    """
    Fraction of expected entity values found in the output string.
    Case-insensitive token matching.
    """
    output_lower = output.lower()
    total = 0
    found = 0

    def _check(val: Any) -> None:
        nonlocal total, found
        total += 1
        if str(val).lower() in output_lower:
            found += 1

    for values in expected.values():
        if isinstance(values, list):
            for v in values:
                _check(v if not isinstance(v, dict) else list(v.values())[0])
        else:
            _check(values)

    return found / total if total > 0 else 0.0


def _stub_extraction_output(text: str) -> str:
    """Minimal stub for when the extraction service is not available."""
    import json
    return json.dumps({
        "diagnoses":    [],
        "medications":  [],
        "lab_values":   [],
        "icd_codes":    [],
        "input_length": len(text),
        "_stub":        True,
    })
