"""
Confidence-aware model router.

Selects the initial model tier for a reasoning request based on case
complexity signals.  The escalation engine handles upgrades mid-flight;
this router determines the starting tier.

Routing signals:
  - Extraction confidence from the state
  - Number of undetermined criteria (from prior attempts, if any)
  - Number of policies to evaluate
  - Whether this is a re-run after guardrail failure
  - Case service type complexity score

Tier mapping:
  SMALL  → High-confidence extraction, few criteria, no prior failures
  MEDIUM → Moderate confidence or moderate complexity (default)
  LARGE  → Low confidence, many policies, prior escalation, complex service

Provider abstraction:
  The router returns a ModelConfig (not an API client).
  The pipeline instantiates the actual client based on the provider field.
"""

from __future__ import annotations

import structlog

from app.services.reasoning.models import (
    LARGE_MODEL_CONFIG,
    MEDIUM_MODEL_CONFIG,
    MODEL_TIER_MAP,
    SMALL_MODEL_CONFIG,
    ModelConfig,
    ModelTier,
    ViolationType,
)

logger = structlog.get_logger(__name__)

# -----------------------------------------------------------------------
# Routing thresholds
# -----------------------------------------------------------------------

# Extraction confidence thresholds
SMALL_MIN_EXTRACTION_CONFIDENCE  = 0.85
MEDIUM_MIN_EXTRACTION_CONFIDENCE = 0.60

# Policy count thresholds
SMALL_MAX_POLICIES  = 1
MEDIUM_MAX_POLICIES = 3

# Criteria count thresholds
SMALL_MAX_CRITERIA  = 5
MEDIUM_MAX_CRITERIA = 12

# Escalation-triggering service types (complex PA categories)
COMPLEX_SERVICE_TYPES = {
    "organ transplant",
    "experimental",
    "investigational",
    "gene therapy",
    "car-t",
    "oncology",
    "rare disease",
    "orphan drug",
}


# -----------------------------------------------------------------------
# Router context
# -----------------------------------------------------------------------

from dataclasses import dataclass, field


@dataclass
class RouterContext:
    """
    Input signals for the model router decision.

    Populated from the workflow state before the first LLM call.
    """
    case_id:                    str
    extraction_confidence:      float = 1.0   # avg across entities
    policy_count:               int   = 0
    criteria_count:             int   = 0
    service_type:               str   = ""
    prior_attempt_count:        int   = 0
    prior_violation_types:      list[str] = field(default_factory=list)
    clarification_attempt_count: int  = 0


# -----------------------------------------------------------------------
# Model router
# -----------------------------------------------------------------------

class ModelRouter:
    """
    Selects the initial LLM tier for a reasoning request.

    Rules are evaluated in priority order; first match wins:
      1. LARGE if prior HIGH/CRITICAL violations or service is complex
      2. LARGE if extraction confidence very low
      3. SMALL if all conditions for low-complexity are met
      4. MEDIUM otherwise (default)
    """

    def __init__(self, tier_map: dict[ModelTier, ModelConfig] | None = None) -> None:
        self._map = tier_map or MODEL_TIER_MAP

    def route(self, ctx: RouterContext) -> ModelConfig:
        """
        Determine which model tier to start with.

        Returns:
            ModelConfig ready to pass to the LLM provider client.
        """
        tier = self._select_tier(ctx)

        logger.info(
            "router.model_selected",
            case_id=ctx.case_id,
            tier=tier.value,
            model_id=self._map[tier].model_id,
            signals={
                "extraction_conf": round(ctx.extraction_confidence, 3),
                "policies": ctx.policy_count,
                "criteria": ctx.criteria_count,
                "prior_attempts": ctx.prior_attempt_count,
                "service_type": ctx.service_type,
            },
        )
        return self._map[tier]

    def _select_tier(self, ctx: RouterContext) -> ModelTier:
        # Rule 1: Prior HIGH/CRITICAL violations → start at LARGE
        high_severity_violations = {
            ViolationType.HALLUCINATION.value,
            ViolationType.SCHEMA_INVALID.value,
            ViolationType.GROUNDEDNESS_FAILURE.value,
            ViolationType.UNSAFE_CONTENT.value,
        }
        if any(v in high_severity_violations for v in ctx.prior_violation_types):
            return ModelTier.LARGE

        # Rule 2: Complex service type → LARGE
        svc = ctx.service_type.lower()
        if any(cst in svc for cst in COMPLEX_SERVICE_TYPES):
            return ModelTier.LARGE

        # Rule 3: Multiple prior escalations → LARGE
        if ctx.prior_attempt_count >= 2:
            return ModelTier.LARGE

        # Rule 4: Very low extraction confidence → LARGE
        if ctx.extraction_confidence < MEDIUM_MIN_EXTRACTION_CONFIDENCE:
            return ModelTier.LARGE

        # Rule 5: Moderate confidence + moderate complexity → MEDIUM
        if ctx.extraction_confidence < SMALL_MIN_EXTRACTION_CONFIDENCE:
            return ModelTier.MEDIUM
        if ctx.policy_count > SMALL_MAX_POLICIES:
            return ModelTier.MEDIUM
        if ctx.criteria_count > SMALL_MAX_CRITERIA:
            return ModelTier.MEDIUM
        if ctx.clarification_attempt_count > 0:
            return ModelTier.MEDIUM

        # Rule 6: All simple signals → SMALL
        return ModelTier.SMALL

    def escalate(self, current_tier: ModelTier) -> ModelConfig | None:
        """
        Return the next tier up, or None if already at LARGE.

        Used by the escalation engine when a guardrail failure requires a
        stronger model.
        """
        if current_tier == ModelTier.SMALL:
            return self._map[ModelTier.MEDIUM]
        if current_tier == ModelTier.MEDIUM:
            return self._map[ModelTier.LARGE]
        return None  # already at LARGE
