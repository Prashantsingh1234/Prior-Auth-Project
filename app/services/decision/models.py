"""
Data models for the decision engine.

These are internal to the decision service.  The workflow layer continues to
use PARecommendation from state/models.py — these models carry the richer
intermediate representations produced during rule evaluation, confidence
calculation, and override processing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DecisionVerdict(str, Enum):
    """Final decision outcome from the rules engine."""
    APPROVE               = "approve"
    DENY                  = "deny"
    PEND_FOR_INFO         = "pend_for_info"
    REFER_MEDICAL_DIRECTOR = "refer_medical_director"


class DecisionRuleType(str, Enum):
    """Which rule fired to produce the verdict."""
    ALL_PASS              = "all_pass"           # All determinate criteria MET
    ANY_FAIL              = "any_fail"           # At least one criterion NOT_MET
    MISSING_INFO          = "missing_info"       # Undetermined criteria present
    LOW_CONFIDENCE        = "low_confidence"     # Confidence below auto-decision threshold
    NO_CRITERIA           = "no_criteria"        # No criteria evaluated
    ALL_NOT_APPLICABLE    = "all_not_applicable" # All criteria are N/A
    OVERRIDE              = "override"           # Reviewer override applied
    POLICY_CONFLICT       = "policy_conflict"    # Conflicting signals across policies


class ConfidenceFlag(str, Enum):
    """Flags that affect confidence calculation."""
    HIGH_CRITERION_AGREEMENT  = "high_criterion_agreement"
    HIGH_EVIDENCE_QUALITY     = "high_evidence_quality"
    UNDETERMINED_CRITERIA     = "undetermined_criteria"
    LOW_EXTRACTION_CONFIDENCE = "low_extraction_confidence"
    MISSING_EVIDENCE          = "missing_evidence"
    CROSS_POLICY_CONFLICT     = "cross_policy_conflict"
    SINGLE_CRITERION          = "single_criterion"
    PARTIAL_COVERAGE          = "partial_coverage"


# ---------------------------------------------------------------------------
# Per-criterion decision
# ---------------------------------------------------------------------------

@dataclass
class CriterionDecision:
    """Rule engine's view of a single criterion evaluation."""
    criterion_id:    str
    criterion_text:  str
    criterion_type:  str | None
    status:          str    # "met" | "not_met" | "undetermined" | "not_applicable"
    confidence:      float  # 0.0–1.0
    evidence:        list[str] = field(default_factory=list)
    policy_section:  str | None = None
    notes:           str | None = None
    is_blocking:     bool = False  # True for critical criterion types


# ---------------------------------------------------------------------------
# Confidence breakdown
# ---------------------------------------------------------------------------

@dataclass
class ConfidenceBreakdown:
    """
    Detailed breakdown of how the final confidence score was derived.

    Used in rationale generation and audit logging.
    """
    final_score:             float

    # Component scores (each 0.0–1.0)
    criterion_confidence_avg: float = 0.0    # Average CriterionEvaluation.confidence
    coverage_score:           float = 0.0    # Fraction of criteria that are determinate
    evidence_quality_score:   float = 0.0    # Fraction of met/not-met with evidence quotes
    extraction_confidence:    float = 0.0    # From ExtractedEntities.overall_confidence

    # Penalty/bonus accounting
    penalties:               float = 0.0    # Sum of applied penalties (positive = reduction)
    bonuses:                 float = 0.0    # Sum of applied bonuses (positive = increase)

    # Flags that were triggered
    flags:                   list[ConfidenceFlag] = field(default_factory=list)

    # Counts used in calculation
    total_criteria:          int = 0
    met_count:               int = 0
    not_met_count:           int = 0
    undetermined_count:      int = 0
    not_applicable_count:    int = 0
    criteria_with_evidence:  int = 0


# ---------------------------------------------------------------------------
# Decision rule match
# ---------------------------------------------------------------------------

@dataclass
class RuleMatch:
    """
    Record of which rule fired and why.

    Multiple rules may be evaluated; only the highest-priority match
    determines the verdict.
    """
    rule_type:       DecisionRuleType
    verdict:         DecisionVerdict
    triggered_by:    str    # Human-readable explanation of why this rule fired
    blocking_criteria: list[str] = field(default_factory=list)  # criterion_ids for DENY
    missing_criteria:  list[str] = field(default_factory=list)  # criterion_ids for PEND


# ---------------------------------------------------------------------------
# Primary decision output
# ---------------------------------------------------------------------------

@dataclass
class DecisionResult:
    """
    Full structured output from the decision engine for one case.

    Maps to PARecommendation for workflow state storage via
    DecisionEngine.to_recommendation().
    """
    decision_id:          str = field(default_factory=lambda: str(uuid4()))
    verdict:              DecisionVerdict = DecisionVerdict.PEND_FOR_INFO
    rule_applied:         DecisionRuleType = DecisionRuleType.MISSING_INFO
    confidence:           ConfidenceBreakdown = field(default_factory=lambda: ConfidenceBreakdown(0.0))

    # Per-criterion breakdown
    criterion_decisions:  list[CriterionDecision] = field(default_factory=list)

    # Structured rationale
    rationale_lines:      list[str] = field(default_factory=list)   # Ordered reasoning steps
    supporting_criteria:  list[str] = field(default_factory=list)   # criterion_text for MET
    denying_criteria:     list[str] = field(default_factory=list)   # criterion_text for NOT_MET
    evidence_references:  list[str] = field(default_factory=list)   # Evidence quote excerpts

    # Review routing
    requires_human_review: bool = True
    review_reason:         str | None = None

    # Metadata
    policies_evaluated:    int = 0
    criteria_total:        int = 0
    model_used:            str | None = None
    tokens_used:           int = 0
    decided_at:            datetime = field(default_factory=lambda: datetime.now(UTC))
    is_override:           bool = False

    @property
    def confidence_score(self) -> float:
        return round(self.confidence.final_score, 4)

    @property
    def is_approval(self) -> bool:
        return self.verdict == DecisionVerdict.APPROVE

    @property
    def is_denial(self) -> bool:
        return self.verdict == DecisionVerdict.DENY

    @property
    def needs_info(self) -> bool:
        return self.verdict == DecisionVerdict.PEND_FOR_INFO


# ---------------------------------------------------------------------------
# Override models
# ---------------------------------------------------------------------------

@dataclass
class OverrideRequest:
    """
    A reviewer's request to override the AI decision.

    Validated by OverrideHandler before being applied.
    """
    reviewer_id:          str
    reviewer_name:        str | None
    target_verdict:       DecisionVerdict   # What the reviewer wants it to be
    override_reason:      str              # Required free-text justification
    clinical_notes:       str = ""
    regulatory_citation:  str = ""        # e.g., "Medicare LCD L34822"
    requested_at:         datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class OverrideDecision:
    """
    Result of applying an override to an existing DecisionResult.

    Wraps the modified DecisionResult with provenance tracking.
    """
    original_result:      DecisionResult
    override_request:     OverrideRequest
    final_result:         DecisionResult
    override_applied:     bool = True
    validation_errors:    list[str] = field(default_factory=list)
    override_id:          str = field(default_factory=lambda: str(uuid4()))
    applied_at:           datetime = field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Decision input (assembled from PAWorkflowState by the engine)
# ---------------------------------------------------------------------------

@dataclass
class DecisionInput:
    """
    Normalised input to the decision engine, assembled from PAWorkflowState.

    Decouples the engine from the LangGraph state schema — fully testable
    without a running graph.
    """
    case_id:               str
    service_type:          str
    evaluation_results:    dict[str, Any]    # dict[str, EvaluationResult]
    clarification_attempts: list[Any]        # list[ClarificationAttempt]
    extraction_confidence:  float            # avg from ExtractedEntities
    prior_recommendation:   Any | None       # PARecommendation from reasoning pipeline
    model_used:             str | None = None
    tokens_used:            int = 0
