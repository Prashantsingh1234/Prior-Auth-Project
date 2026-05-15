"""
PA Decision Engine package.

Deterministic, multi-factor prior authorization decision engine.

Quick start:
    from app.services.decision import DecisionEngine

    engine = DecisionEngine()

    # Make an AI decision
    result = await engine.decide(state, case_id=case_id)
    recommendation = engine.to_recommendation(result)

    # Apply reviewer override
    override_req = OverrideRequest(
        reviewer_id="rev-001",
        reviewer_name="Dr. Smith",
        target_verdict=DecisionVerdict.APPROVE,
        override_reason="Patient meets criteria based on updated lab values received via phone.",
    )
    override = engine.apply_override(result, override_req)
    if override.override_applied:
        final_rec = engine.to_recommendation(override.final_result)
"""

from app.services.decision.confidence import ConfidenceCalculator
from app.services.decision.engine import DecisionEngine, get_decision_engine
from app.services.decision.models import (
    ConfidenceBreakdown,
    ConfidenceFlag,
    CriterionDecision,
    DecisionInput,
    DecisionResult,
    DecisionRuleType,
    DecisionVerdict,
    OverrideDecision,
    OverrideRequest,
    RuleMatch,
)
from app.services.decision.override import OverrideHandler
from app.services.decision.rationale import RationaleFormatter
from app.services.decision.rules import DecisionRulesEngine

__all__ = [
    # Primary engine
    "DecisionEngine",
    "get_decision_engine",
    # Sub-components
    "DecisionRulesEngine",
    "ConfidenceCalculator",
    "RationaleFormatter",
    "OverrideHandler",
    # Models
    "DecisionVerdict",
    "DecisionRuleType",
    "ConfidenceFlag",
    "CriterionDecision",
    "ConfidenceBreakdown",
    "RuleMatch",
    "DecisionResult",
    "DecisionInput",
    "OverrideRequest",
    "OverrideDecision",
]
