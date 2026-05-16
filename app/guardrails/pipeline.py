"""
Guardrail pipeline — orchestrates all detectors for pre-LLM and post-LLM stages.

GuardrailPipeline is the single entry point for all guardrail enforcement.
Nodes call it before and after LLM invocations:

    pipeline = GuardrailPipeline.for_node("reasoning_node")

    # Before LLM call
    pre_result = await pipeline.check_input(prompt, state)
    if pre_result.blocked:
        return fallback_response(pre_result)

    # Call LLM
    output = await llm.invoke(prompt)

    # After LLM call
    post_result = await pipeline.check_output(output, state, retrieved_docs=docs)
    if post_result.blocked:
        return fallback_response(post_result)

    return output if post_result.sanitized_content is None else post_result.sanitized_content

All detector failures are swallowed — guardrail errors must never break the
workflow.  Violations are logged, escalated, and audited regardless.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from app.guardrails.config import GuardrailPolicy, get_policy_for_node
from app.guardrails.detectors.jailbreak import detect_jailbreak
from app.guardrails.detectors.output_safety import detect_unsafe_output
from app.guardrails.detectors.pii import detect_pii, find_pii_entities
from app.guardrails.detectors.policy_grounding import detect_policy_grounding_failure
from app.guardrails.detectors.prompt_injection import detect_prompt_injection
from app.guardrails.detectors.retrieval_poisoning import (
    RetrievedDocument,
    detect_retrieval_poisoning,
)
from app.guardrails.detectors.schema_validator import detect_schema_violation
from app.guardrails.models import (
    GuardrailResult,
    GuardrailStage,
    GuardrailViolation,
    ViolationSeverity,
    ViolationType,
)

logger = structlog.get_logger(__name__)


class GuardrailPipeline:
    """
    Async guardrail pipeline for a specific workflow node.

    One instance per node — created via GuardrailPipeline.for_node().
    """

    def __init__(
        self,
        node_name: str,
        policy: GuardrailPolicy,
        case_id: str | None = None,
    ) -> None:
        self._node_name = node_name
        self._policy    = policy
        self._case_id   = case_id
        self._log = structlog.get_logger(__name__).bind(
            node=node_name, case_id=case_id
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check_input(
        self,
        prompt: str,
        state: dict[str, Any] | None = None,
    ) -> GuardrailResult:
        """
        Run all pre-LLM guardrail detectors on the prompt text.

        Checks: prompt injection, jailbreak, PII in prompt.
        """
        t0 = time.monotonic()
        violations: list[GuardrailViolation] = []

        tasks: list[Any] = []
        policy = self._policy

        if policy.detector_enabled(ViolationType.PROMPT_INJECTION):
            tasks.append(detect_prompt_injection(
                prompt,
                threshold=policy.thresholds.prompt_injection,
                stage=GuardrailStage.PRE_LLM,
            ))
        if policy.detector_enabled(ViolationType.JAILBREAK):
            tasks.append(detect_jailbreak(
                prompt,
                threshold=policy.thresholds.jailbreak,
                stage=GuardrailStage.PRE_LLM,
            ))
        if policy.detector_enabled(ViolationType.PII_LEAKAGE) and policy.sanitizer.sanitize_pii_in_prompts:
            tasks.append(detect_pii(
                prompt,
                threshold=policy.thresholds.pii_detection,
                stage=GuardrailStage.PRE_LLM,
            ))

        results = await _gather_safe(tasks)
        violations = [r for r in results if r is not None]

        return self._build_result(
            violations=violations,
            stage=GuardrailStage.PRE_LLM,
            content=prompt,
            elapsed_ms=(time.monotonic() - t0) * 1000,
        )

    async def check_output(
        self,
        output: str | dict[str, Any],
        state: dict[str, Any] | None = None,
        retrieved_docs: list[RetrievedDocument] | None = None,
        node_name: str | None = None,
    ) -> GuardrailResult:
        """
        Run all post-LLM guardrail detectors on LLM output.

        Checks: unsafe output, PII leakage, policy grounding, schema.
        Optionally sanitizes PII from output before returning.
        """
        t0 = time.monotonic()
        violations: list[GuardrailViolation] = []
        policy = self._policy
        effective_node = node_name or self._node_name

        output_str = output if isinstance(output, str) else str(output)
        output_dict = output if isinstance(output, dict) else None

        tasks: list[Any] = []

        if policy.detector_enabled(ViolationType.UNSAFE_OUTPUT):
            tasks.append(detect_unsafe_output(
                output_str,
                threshold=policy.thresholds.output_safety,
                stage=GuardrailStage.POST_LLM,
            ))

        if policy.detector_enabled(ViolationType.PII_LEAKAGE):
            tasks.append(detect_pii(
                output_str,
                threshold=policy.thresholds.pii_detection,
                stage=GuardrailStage.POST_LLM,
            ))

        if policy.detector_enabled(ViolationType.POLICY_GROUNDING_FAILURE):
            doc_ids = [d.doc_id for d in (retrieved_docs or [])]
            tasks.append(detect_policy_grounding_failure(
                output_str,
                retrieved_doc_ids=doc_ids,
                threshold=policy.thresholds.policy_grounding,
                stage=GuardrailStage.POST_LLM,
            ))

        if policy.detector_enabled(ViolationType.SCHEMA_VIOLATION) and output_dict is not None:
            tasks.append(detect_schema_violation(
                output_dict,
                node_name=effective_node,
                stage=GuardrailStage.POST_LLM,
            ))

        results = await _gather_safe(tasks)
        violations = [r for r in results if r is not None]

        # Sanitize PII from output if policy allows
        sanitized_content: str | None = None
        pii_violations = [v for v in violations if v.violation_type == ViolationType.PII_LEAKAGE]
        if pii_violations and policy.sanitizer.sanitize_pii_in_output and policy.sanitizer.allow_partial_sanitize:
            sanitized_content = _mask_pii_in_text(output_str)
            violations = [v for v in violations if v.violation_type != ViolationType.PII_LEAKAGE]
            self._log.debug("guardrail.pii_sanitized", original_len=len(output_str))

        return self._build_result(
            violations=violations,
            stage=GuardrailStage.POST_LLM,
            content=output_str,
            elapsed_ms=(time.monotonic() - t0) * 1000,
            sanitized_content=sanitized_content,
        )

    async def check_retrieval(
        self,
        documents: list[RetrievedDocument],
    ) -> GuardrailResult:
        """Run retrieval poisoning detection on retrieved documents."""
        t0 = time.monotonic()
        violations: list[GuardrailViolation] = []
        policy = self._policy

        if policy.detector_enabled(ViolationType.RETRIEVAL_POISONING):
            try:
                v = await detect_retrieval_poisoning(
                    documents,
                    threshold=policy.thresholds.retrieval_anomaly,
                    stage=GuardrailStage.PRE_RETRIEVAL,
                )
                if v:
                    violations.append(v)
            except Exception as exc:
                self._log.warning("guardrail.retrieval_check_error", error=str(exc))

        return self._build_result(
            violations=violations,
            stage=GuardrailStage.PRE_RETRIEVAL,
            elapsed_ms=(time.monotonic() - t0) * 1000,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_result(
        self,
        violations: list[GuardrailViolation],
        stage: GuardrailStage,
        content: str = "",
        elapsed_ms: float = 0.0,
        sanitized_content: str | None = None,
    ) -> GuardrailResult:
        policy = self._policy

        # Determine blocking and escalation
        blocking = [v for v in violations if policy.should_block(v.severity)]
        escalate_set = [v for v in violations if policy.should_escalate(v.severity)]

        # Combined block: too many medium+ violations
        medium_plus = [v for v in violations if v.severity >= ViolationSeverity.MEDIUM]
        auto_block_from_combined = len(medium_plus) >= policy.escalation.combined_block_count

        blocked   = bool(blocking) or auto_block_from_combined
        escalated = bool(escalate_set) or blocked
        passed    = not bool(violations)

        result = GuardrailResult(
            passed=passed,
            blocked=blocked,
            escalated=escalated,
            violations=violations,
            sanitized_content=sanitized_content,
            stage=stage,
            processing_ms=round(elapsed_ms, 1),
            case_id=self._case_id,
            node_name=self._node_name,
        )

        if violations:
            self._log.warning(
                "guardrail.violations_detected",
                count=len(violations),
                blocked=blocked,
                escalated=escalated,
                stage=stage.value,
                types=[v.violation_type.value for v in violations],
                elapsed_ms=round(elapsed_ms, 1),
            )
            _emit_prometheus(violations, self._node_name, blocked)
        else:
            self._log.debug(
                "guardrail.passed",
                stage=stage.value,
                elapsed_ms=round(elapsed_ms, 1),
            )

        return result

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def for_node(
        cls,
        node_name: str,
        case_id: str | None = None,
        policy: GuardrailPolicy | None = None,
    ) -> "GuardrailPipeline":
        effective_policy = policy or get_policy_for_node(node_name)
        return cls(node_name=node_name, policy=effective_policy, case_id=case_id)

    @classmethod
    def with_policy(
        cls,
        policy: GuardrailPolicy,
        node_name: str = "unknown",
        case_id: str | None = None,
    ) -> "GuardrailPipeline":
        return cls(node_name=node_name, policy=policy, case_id=case_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _gather_safe(coroutines: list[Any]) -> list[GuardrailViolation | None]:
    """Run coroutines concurrently; swallow individual failures."""
    if not coroutines:
        return []
    results: list[GuardrailViolation | None] = []
    for coro_result in await asyncio.gather(*coroutines, return_exceptions=True):
        if isinstance(coro_result, Exception):
            logger.warning("guardrail.detector_error", error=str(coro_result))
            results.append(None)
        else:
            results.append(coro_result)
    return results


def _mask_pii_in_text(text: str) -> str:
    """Replace detected PII entities with type-labelled masks."""
    entities = find_pii_entities(text)
    if not entities:
        return text

    # Sort by position descending so replacements don't shift offsets
    entities.sort(key=lambda e: e.start, reverse=True)
    chars = list(text)
    for entity in entities:
        mask = f"[{entity.entity_type.upper()}_REDACTED]"
        chars[entity.start:entity.end] = list(mask)
    return "".join(chars)


def _emit_prometheus(
    violations: list[GuardrailViolation],
    node_name: str,
    blocked: bool,
) -> None:
    try:
        from app.guardrails.observability import (
            GUARDRAIL_VIOLATIONS_TOTAL,
            GUARDRAIL_BLOCKS_TOTAL,
        )
        for v in violations:
            GUARDRAIL_VIOLATIONS_TOTAL.labels(
                node=node_name,
                violation_type=v.violation_type.value,
                severity=v.severity.value,
            ).inc()
        if blocked:
            GUARDRAIL_BLOCKS_TOTAL.labels(node=node_name).inc()
    except Exception:
        pass
