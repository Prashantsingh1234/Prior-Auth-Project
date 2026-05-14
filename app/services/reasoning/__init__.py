"""
PA Reasoning Engine package.

Multi-model, guardrail-enforced AI reasoning for prior authorization evaluation.

Quick start:
    from app.services.reasoning import ReasoningPipeline

    pipeline = ReasoningPipeline.from_settings()
    result = await pipeline.evaluate_policy(policy, state, case_id=case_id, clinical_summary=summary)
    if result.succeeded:
        eval_result = pipeline.convert_to_evaluation_result(result, policy, result.final_tier.value)
        recommendation = pipeline.build_recommendation({eval_result.dedup_key: eval_result}, result)
    else:
        # result.requires_human_escalation is True — route to human review
        pass
"""

from app.services.reasoning.escalation import EscalationDecision, EscalationEngine
from app.services.reasoning.models import (
    LARGE_MODEL_CONFIG,
    MEDIUM_MODEL_CONFIG,
    MODEL_TIER_MAP,
    SMALL_MODEL_CONFIG,
    CriterionReasoningResult,
    CriterionStatus,
    EscalationTrigger,
    EvidenceCitation,
    GuardrailResult,
    GuardrailViolation,
    ModelConfig,
    ModelProvider,
    ModelTier,
    ReasoningAttempt,
    ReasoningOutput,
    ReasoningResult,
    ViolationSeverity,
    ViolationType,
)
from app.services.reasoning.orchestrator import MultiModelOrchestrator
from app.services.reasoning.pipeline import ReasoningPipeline
from app.services.reasoning.router import ModelRouter, RouterContext

__all__ = [
    # Primary interface
    "ReasoningPipeline",
    "MultiModelOrchestrator",
    # Models
    "ModelTier",
    "ModelProvider",
    "ModelConfig",
    "CriterionStatus",
    "CriterionReasoningResult",
    "EvidenceCitation",
    "ReasoningOutput",
    "ReasoningResult",
    "ReasoningAttempt",
    "GuardrailResult",
    "GuardrailViolation",
    "ViolationType",
    "ViolationSeverity",
    "EscalationTrigger",
    # Router
    "ModelRouter",
    "RouterContext",
    # Escalation
    "EscalationEngine",
    "EscalationDecision",
    # Tier configs
    "SMALL_MODEL_CONFIG",
    "MEDIUM_MODEL_CONFIG",
    "LARGE_MODEL_CONFIG",
    "MODEL_TIER_MAP",
]
