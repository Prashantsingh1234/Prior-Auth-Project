"""
Multi-model orchestration layer.

Coordinates model routing → LLM call → guardrail validation → escalation
into a single async flow.  Manages the attempt loop and tracks cost.

Flow:
  1. RouterContext is built from workflow state signals
  2. ModelRouter picks initial tier (SMALL | MEDIUM | LARGE)
  3. For each attempt (up to MAX_ATTEMPTS):
       a. Call LLM with selected ModelConfig
       b. Run PreLLM and PostLLM validators
       c. If guardrails pass → return ReasoningResult
       d. EscalationEngine decides: retry (stronger model) or human review
  4. If human review required → return escalated ReasoningResult

Cost tracking:
  - prompt_tokens + completion_tokens per attempt
  - estimated_cost_usd computed on result
  - all tracked via Prometheus counters

Observability:
  - Every attempt logged with tier, tokens, latency, violations
  - Prometheus metrics for escalations, guardrail failures, per-tier token usage
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from app.services.reasoning.escalation import EscalationEngine, EscalationRecord
from app.services.reasoning.guardrails.base import GuardrailContext
from app.services.reasoning.guardrails.post_llm import PostLLMValidator
from app.services.reasoning.guardrails.pre_llm import InputValidator
from app.services.reasoning.models import (
    MEDIUM_MODEL_CONFIG,
    MODEL_TIER_MAP,
    ModelConfig,
    ModelTier,
    ReasoningAttempt,
    ReasoningOutput,
    ReasoningResult,
)
from app.services.reasoning.router import ModelRouter, RouterContext

logger = structlog.get_logger(__name__)

# Maximum attempts across all tiers before giving up
MAX_ATTEMPTS = 4


class MultiModelOrchestrator:
    """
    Orchestrates multi-tier LLM reasoning with automatic escalation.

    Usage:
        orchestrator = MultiModelOrchestrator.from_settings()
        result = await orchestrator.reason(
            case_id="PA-001",
            prompt_builder=my_prompt_fn,
            guardrail_ctx=ctx,
            router_ctx=router_ctx,
        )
    """

    def __init__(
        self,
        router:     ModelRouter | None = None,
        escalation: EscalationEngine | None = None,
        validator:  PostLLMValidator | None = None,
        pre_validator: InputValidator | None = None,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> None:
        self._router    = router or ModelRouter()
        self._escalation = escalation or EscalationEngine()
        self._validator = validator or PostLLMValidator()
        self._pre       = pre_validator or InputValidator()
        self._max_attempts = max_attempts
        self._log = structlog.get_logger(self.__class__.__name__)

    async def reason(
        self,
        *,
        case_id: str,
        system_prompt: str,
        user_prompt_builder,  # Callable[[ModelTier, int], str] — builds user prompt
        guardrail_ctx: GuardrailContext,
        router_ctx: RouterContext,
    ) -> ReasoningResult:
        """
        Run the full multi-model reasoning loop for a single policy evaluation.

        Args:
            case_id:             PA case identifier.
            system_prompt:       System prompt string (tier-aware; caller selects STANDARD/ADVANCED).
            user_prompt_builder: Callable(tier, attempt_num) → user prompt string.
            guardrail_ctx:       Guardrail context with source docs for grounding.
            router_ctx:          Routing signals from workflow state.

        Returns:
            ReasoningResult with output, attempts, cost, escalation info.
        """
        t0 = time.perf_counter()

        # --- Pre-LLM input validation ---
        pre_result = await self._pre.check(guardrail_ctx)
        if not pre_result.passed:
            self._log.warning(
                "orchestrator.pre_validation_failed",
                case_id=case_id,
                violations=[v.violation_type.value for v in pre_result.violations],
            )
            # Pre-validation failure = escalate to human without trying LLM
            return ReasoningResult(
                output=None,
                attempts=[],
                final_tier=ModelTier.MEDIUM,
                escalations_count=0,
                total_prompt_tokens=0,
                total_completion_tokens=0,
                total_latency_ms=(time.perf_counter() - t0) * 1000,
                requires_human_escalation=True,
                escalation_reason="Pre-LLM input validation failed: " + "; ".join(
                    v.message for v in pre_result.violations[:3]
                ),
                guardrail_violations=pre_result.violations,
            )

        # --- Routing: select initial model tier ---
        model_config = self._router.route(router_ctx)
        current_tier = model_config.tier

        attempts: list[ReasoningAttempt] = []
        escalation_history: list[EscalationRecord] = []
        all_violations = list(pre_result.violations)

        for attempt_num in range(1, self._max_attempts + 1):
            self._log.info(
                "orchestrator.attempt_start",
                case_id=case_id,
                attempt=attempt_num,
                tier=current_tier.value,
                model_id=model_config.model_id,
            )

            # Build prompts (may differ by tier for advanced models)
            user_prompt = user_prompt_builder(current_tier, attempt_num)

            # Call LLM
            attempt_t0 = time.perf_counter()
            raw_output, prompt_tokens, completion_tokens, call_error = (
                await self._call_llm(
                    model_config=model_config,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    case_id=case_id,
                )
            )
            attempt_latency = (time.perf_counter() - attempt_t0) * 1000

            # Handle provider errors
            if call_error:
                attempt = ReasoningAttempt(
                    attempt_number=attempt_num,
                    model_tier=current_tier,
                    model_id=model_config.model_id,
                    raw_output=None,
                    parsed_output=None,
                    guardrail_result=None,
                    error=call_error,
                    latency_ms=attempt_latency,
                    prompt_tokens=0,
                    completion_tokens=0,
                )
                attempts.append(attempt)
                self._track_attempt_metrics(attempt)

                # Escalate on provider error
                next_config = self._router.escalate(current_tier)
                if next_config:
                    model_config = next_config
                    current_tier = model_config.tier
                else:
                    break
                continue

            # Run post-LLM guardrails
            guardrail_result = await self._validator.validate(
                raw_output=raw_output,
                ctx=guardrail_ctx,
            )
            all_violations.extend(guardrail_result.violations)

            parsed_output = self._parse_output(guardrail_result)
            escalation_trigger = (
                list(guardrail_result.escalation_triggers)[0]
                if guardrail_result.escalation_triggers else None
            )

            attempt = ReasoningAttempt(
                attempt_number=attempt_num,
                model_tier=current_tier,
                model_id=model_config.model_id,
                raw_output=raw_output,
                parsed_output=parsed_output,
                guardrail_result=guardrail_result,
                error=None,
                latency_ms=attempt_latency,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                escalation_trigger=escalation_trigger,
            )
            attempts.append(attempt)
            self._track_attempt_metrics(attempt)

            # If guardrails passed → done
            if guardrail_result.passed and parsed_output is not None:
                self._log.info(
                    "orchestrator.success",
                    case_id=case_id,
                    attempt=attempt_num,
                    tier=current_tier.value,
                    total_tokens=prompt_tokens + completion_tokens,
                )
                return self._build_result(
                    output=parsed_output,
                    attempts=attempts,
                    final_tier=current_tier,
                    escalations=len(escalation_history),
                    all_violations=all_violations,
                    t0=t0,
                    requires_human=False,
                )

            # Evaluate escalation
            decision = self._escalation.evaluate(
                current_tier=current_tier,
                guardrail_result=guardrail_result,
                escalation_history=escalation_history,
                case_id=case_id,
            )

            if decision.human_review:
                return self._build_result(
                    output=None,
                    attempts=attempts,
                    final_tier=current_tier,
                    escalations=len(escalation_history),
                    all_violations=all_violations,
                    t0=t0,
                    requires_human=True,
                    escalation_reason=decision.reason,
                )

            if decision.is_escalate and decision.next_tier:
                self._escalation.record_escalation(
                    escalation_history,
                    attempt_number=attempt_num,
                    from_tier=current_tier,
                    to_tier=decision.next_tier,
                    trigger=decision.trigger,
                    violations=guardrail_result.violations,
                )
                model_config = MODEL_TIER_MAP[decision.next_tier]
                current_tier = model_config.tier
                # Update guardrail context with violation history for next attempt
                guardrail_ctx.prior_violations = all_violations[:]
                guardrail_ctx.attempt_number = attempt_num + 1
            else:
                break  # no more escalations possible

        # Exhausted attempts without success
        self._log.warning(
            "orchestrator.max_attempts_exceeded",
            case_id=case_id,
            attempts=len(attempts),
        )
        return self._build_result(
            output=None,
            attempts=attempts,
            final_tier=current_tier,
            escalations=len(escalation_history),
            all_violations=all_violations,
            t0=t0,
            requires_human=True,
            escalation_reason=f"Max attempts ({self._max_attempts}) exceeded without passing guardrails",
        )

    # ------------------------------------------------------------------
    # LLM call (provider abstraction)
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        *,
        model_config: ModelConfig,
        system_prompt: str,
        user_prompt: str,
        case_id: str,
    ) -> tuple[str, int, int, str | None]:
        """
        Call the LLM and return (raw_output, prompt_tokens, completion_tokens, error).

        Supports OpenAI and Anthropic providers.
        """
        from app.services.reasoning.models import ModelProvider

        try:
            if model_config.provider == ModelProvider.OPENAI:
                return await self._call_openai(model_config, system_prompt, user_prompt)
            elif model_config.provider == ModelProvider.ANTHROPIC:
                return await self._call_anthropic(model_config, system_prompt, user_prompt)
            else:
                return "", 0, 0, f"Unknown provider: {model_config.provider}"
        except asyncio.TimeoutError:
            self._log.error("orchestrator.llm_timeout", case_id=case_id, model=model_config.model_id)
            return "", 0, 0, "LLM call timed out"
        except Exception as exc:
            self._log.error(
                "orchestrator.llm_error",
                case_id=case_id,
                model=model_config.model_id,
                error=str(exc),
            )
            return "", 0, 0, str(exc)

    async def _call_openai(
        self,
        config: ModelConfig,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[str, int, int, None]:
        from openai import AsyncOpenAI
        from app.core.config.settings import get_settings

        settings = get_settings()
        client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=config.timeout_secs,
        )

        # o3-mini does not support response_format=json_object with system role
        is_o_series = config.model_id.startswith("o")
        messages = [
            {"role": "system" if not is_o_series else "user",
             "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if is_o_series:
            # o-series: merge system into user turn
            messages = [{"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}]

        kwargs: dict[str, Any] = {
            "model": config.model_id,
            "messages": messages,
        }
        if not is_o_series:
            kwargs["temperature"] = config.temperature
            kwargs["response_format"] = {"type": "json_object"}
        kwargs["max_completion_tokens"] = config.max_tokens

        response = await asyncio.wait_for(
            client.chat.completions.create(**kwargs),
            timeout=config.timeout_secs,
        )
        content = response.choices[0].message.content or "{}"
        usage = response.usage
        return (
            content,
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
            None,
        )

    async def _call_anthropic(
        self,
        config: ModelConfig,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[str, int, int, None]:
        import anthropic
        from app.core.config.settings import get_settings

        settings = get_settings()
        client = anthropic.AsyncAnthropic(
            api_key=getattr(settings, "anthropic_api_key", "").get_secret_value()
            if hasattr(getattr(settings, "anthropic_api_key", ""), "get_secret_value")
            else getattr(settings, "anthropic_api_key", ""),
        )

        response = await asyncio.wait_for(
            client.messages.create(
                model=config.model_id,
                max_tokens=config.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ),
            timeout=config.timeout_secs,
        )

        content = response.content[0].text if response.content else "{}"
        usage = response.usage
        return (
            content,
            usage.input_tokens if usage else 0,
            usage.output_tokens if usage else 0,
            None,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_output(guardrail_result) -> ReasoningOutput | None:
        """Parse the guardrail-validated dict into a typed ReasoningOutput."""
        corrected = guardrail_result.corrected_output
        if not corrected:
            return None
        try:
            from app.services.reasoning.models import (
                CriterionReasoningResult,
                CriterionStatus,
                EvidenceCitation,
            )
            evals = []
            for ev in corrected.get("criterion_evaluations", []):
                citations = [
                    EvidenceCitation(
                        document_id=c.get("document_id", "unknown"),
                        quote=c.get("quote", ""),
                        relevance_explanation=c.get("relevance_explanation", ""),
                        section=c.get("section"),
                    )
                    for c in ev.get("evidence_citations", [])
                    if isinstance(c, dict)
                ]
                try:
                    status = CriterionStatus(ev.get("status", "UNDETERMINED"))
                except ValueError:
                    status = CriterionStatus.UNDETERMINED

                evals.append(CriterionReasoningResult(
                    criterion_id=ev.get("criterion_id", ""),
                    criterion_text=ev.get("criterion_text", ""),
                    criterion_type=ev.get("criterion_type", "coverage_criteria"),
                    status=status,
                    confidence=float(ev.get("confidence", 0.5)),
                    evidence_citations=citations,
                    rationale=ev.get("rationale", ""),
                    requires_clarification=bool(ev.get("requires_clarification", False)),
                    clarification_question=ev.get("clarification_question"),
                    missing_information=ev.get("missing_information") or [],
                    policy_section=ev.get("policy_section"),
                ))

            return ReasoningOutput(
                criterion_evaluations=evals,
                overall_confidence=float(corrected.get("overall_confidence", 0.5)),
                overall_rationale=corrected.get("overall_rationale", ""),
                requires_human_review=bool(corrected.get("requires_human_review", False)),
                review_reason=corrected.get("review_reason"),
                missing_evidence=corrected.get("missing_evidence") or [],
                reasoning_quality=float(corrected.get("reasoning_quality", 0.5)),
            )
        except Exception:
            return None

    @staticmethod
    def _build_result(
        *,
        output,
        attempts,
        final_tier,
        escalations,
        all_violations,
        t0,
        requires_human,
        escalation_reason=None,
    ) -> ReasoningResult:
        return ReasoningResult(
            output=output,
            attempts=attempts,
            final_tier=final_tier,
            escalations_count=escalations,
            total_prompt_tokens=sum(a.prompt_tokens for a in attempts),
            total_completion_tokens=sum(a.completion_tokens for a in attempts),
            total_latency_ms=(time.perf_counter() - t0) * 1000,
            requires_human_escalation=requires_human,
            escalation_reason=escalation_reason,
            guardrail_violations=all_violations,
        )

    def _track_attempt_metrics(self, attempt: ReasoningAttempt) -> None:
        try:
            from app.monitoring.metrics import (
                LLM_LATENCY_SECONDS,
                LLM_TOKENS_TOTAL,
                REASONING_ATTEMPTS_TOTAL,
            )
            LLM_LATENCY_SECONDS.labels(
                operation=f"reasoning_{attempt.model_tier.value}"
            ).observe(attempt.latency_ms / 1000)
            LLM_TOKENS_TOTAL.labels(
                operation=f"reasoning_{attempt.model_tier.value}",
                token_type="prompt",
            ).inc(attempt.prompt_tokens)
            LLM_TOKENS_TOTAL.labels(
                operation=f"reasoning_{attempt.model_tier.value}",
                token_type="completion",
            ).inc(attempt.completion_tokens)
            REASONING_ATTEMPTS_TOTAL.labels(
                tier=attempt.model_tier.value,
                outcome="success" if attempt.succeeded else "failure",
            ).inc()
        except Exception:
            pass

    @classmethod
    def from_settings(cls) -> "MultiModelOrchestrator":
        """Build an orchestrator from application settings."""
        from app.core.config.settings import get_settings
        settings = get_settings()

        # Allow settings to override model configs
        tier_overrides: dict[ModelTier, ModelConfig] = {}

        small_model = getattr(settings, "reasoning_small_model", None)
        medium_model = getattr(settings, "reasoning_medium_model", None)
        large_model = getattr(settings, "reasoning_large_model", None)

        if small_model:
            from app.services.reasoning.models import (
                ModelProvider, SMALL_MODEL_CONFIG
            )
            from dataclasses import replace
            tier_overrides[ModelTier.SMALL] = SMALL_MODEL_CONFIG.__class__(
                **{**SMALL_MODEL_CONFIG.__dict__, "model_id": small_model}
            )

        return cls(
            router=ModelRouter(),
            escalation=EscalationEngine(
                max_escalations=getattr(settings, "reasoning_max_escalations", MAX_ATTEMPTS),
            ),
            validator=PostLLMValidator(
                min_confidence=getattr(settings, "reasoning_min_confidence", 0.65),
            ),
        )
