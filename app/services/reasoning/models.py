"""
Data models for the AI reasoning engine and guardrail pipeline.

Separate from workflow state models — these are internal to the reasoning
service.  Conversion helpers produce the workflow state models that the
rest of the graph consumes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ModelTier(str, Enum):
    """LLM tier — higher = more capable, slower, more expensive."""
    SMALL  = "small"    # gpt-4o-mini / claude-haiku
    MEDIUM = "medium"   # gpt-4o / claude-sonnet
    LARGE  = "large"    # o3-mini / claude-opus


class ModelProvider(str, Enum):
    OPENAI    = "openai"
    ANTHROPIC = "anthropic"


class CriterionStatus(str, Enum):
    MET           = "MET"
    NOT_MET       = "NOT_MET"
    UNDETERMINED  = "UNDETERMINED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ViolationType(str, Enum):
    SCHEMA_INVALID         = "schema_invalid"
    HALLUCINATION          = "hallucination"
    GROUNDEDNESS_FAILURE   = "groundedness_failure"
    LOW_CONFIDENCE         = "low_confidence"
    UNSAFE_CONTENT         = "unsafe_content"
    MEDICAL_TERMINOLOGY    = "medical_terminology"
    EVIDENCE_MISSING       = "evidence_missing"
    POLICY_INCONSISTENCY   = "policy_inconsistency"
    INPUT_INVALID          = "input_invalid"
    INCOMPLETE_ATTRIBUTION = "incomplete_attribution"
    TIMEOUT                = "timeout"
    PROVIDER_ERROR         = "provider_error"
    TRUNCATED_OUTPUT       = "truncated_output"


class ViolationSeverity(str, Enum):
    LOW      = "low"       # log, continue
    MEDIUM   = "medium"    # escalate model tier
    HIGH     = "high"      # reject output, retry
    CRITICAL = "critical"  # escalate to human review immediately


class EscalationTrigger(str, Enum):
    LOW_CONFIDENCE         = "low_confidence"
    HALLUCINATION_DETECTED = "hallucination_detected"
    SCHEMA_FAILURE         = "schema_failure"
    GROUNDEDNESS_WEAK      = "groundedness_weak"
    EVIDENCE_MISSING       = "evidence_missing"
    PROVIDER_FAILURE       = "provider_failure"
    TIMEOUT                = "timeout"
    REPEATED_VIOLATIONS    = "repeated_violations"
    UNSAFE_OUTPUT          = "unsafe_output"


# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelConfig:
    """Immutable configuration for one LLM endpoint."""
    tier:           ModelTier
    provider:       ModelProvider
    model_id:       str
    max_tokens:     int   = 4096
    temperature:    float = 0.0
    timeout_secs:   float = 60.0
    # Cost per 1K tokens (approximate, for tracking)
    cost_per_1k_prompt:     float = 0.0
    cost_per_1k_completion: float = 0.0


# Default model configs — override via settings
SMALL_MODEL_CONFIG = ModelConfig(
    tier=ModelTier.SMALL,
    provider=ModelProvider.OPENAI,
    model_id="gpt-4o-mini",
    max_tokens=4096,
    temperature=0.0,
    timeout_secs=30.0,
    cost_per_1k_prompt=0.00015,
    cost_per_1k_completion=0.0006,
)

MEDIUM_MODEL_CONFIG = ModelConfig(
    tier=ModelTier.MEDIUM,
    provider=ModelProvider.OPENAI,
    model_id="gpt-4o",
    max_tokens=4096,
    temperature=0.0,
    timeout_secs=60.0,
    cost_per_1k_prompt=0.0025,
    cost_per_1k_completion=0.01,
)

LARGE_MODEL_CONFIG = ModelConfig(
    tier=ModelTier.LARGE,
    provider=ModelProvider.OPENAI,
    model_id="o3-mini",
    max_tokens=8192,
    temperature=1.0,  # o3-mini ignores temperature, set 1.0 as required
    timeout_secs=120.0,
    cost_per_1k_prompt=0.0011,
    cost_per_1k_completion=0.0044,
)

MODEL_TIER_MAP: dict[ModelTier, ModelConfig] = {
    ModelTier.SMALL:  SMALL_MODEL_CONFIG,
    ModelTier.MEDIUM: MEDIUM_MODEL_CONFIG,
    ModelTier.LARGE:  LARGE_MODEL_CONFIG,
}


# ---------------------------------------------------------------------------
# Evidence citation (richer than existing state.models)
# ---------------------------------------------------------------------------

class EvidenceCitation(BaseModel):
    """A direct reference from retrieved policy or clinical document."""
    document_id:          str
    quote:                str = Field(..., description="Verbatim text from source")
    relevance_explanation: str = Field(..., description="Why this evidence supports the determination")
    page_number:          int | None = None
    section:              str | None = None
    confidence:           float = Field(default=1.0, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Per-criterion reasoning output
# ---------------------------------------------------------------------------

class CriterionReasoningResult(BaseModel):
    """
    Rich reasoning result for a single policy criterion.

    This is the per-criterion output from the LLM, before conversion to
    the workflow state's CriterionEvaluation.
    """
    criterion_id:           str
    criterion_text:         str
    criterion_type:         str = "coverage_criteria"
    status:                 CriterionStatus
    confidence:             float = Field(..., ge=0.0, le=1.0)
    evidence_citations:     list[EvidenceCitation] = Field(default_factory=list)
    rationale:              str
    requires_clarification: bool = False
    clarification_question: str | None = None
    missing_information:    list[str] = Field(default_factory=list)
    policy_section:         str | None = None


# ---------------------------------------------------------------------------
# Full reasoning output (structured LLM response)
# ---------------------------------------------------------------------------

class ReasoningOutput(BaseModel):
    """
    Structured output from a single LLM reasoning call.

    Validated by the guardrail pipeline before being accepted.
    """
    criterion_evaluations:  list[CriterionReasoningResult]
    overall_confidence:     float = Field(..., ge=0.0, le=1.0)
    overall_rationale:      str
    requires_human_review:  bool = False
    review_reason:          str | None = None
    missing_evidence:       list[str] = Field(default_factory=list)
    reasoning_quality:      float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("criterion_evaluations")
    @classmethod
    def at_least_one_evaluation(cls, v):
        if not v:
            raise ValueError("criterion_evaluations must not be empty")
        return v

    @property
    def criteria_met_count(self) -> int:
        return sum(1 for e in self.criterion_evaluations if e.status == CriterionStatus.MET)

    @property
    def criteria_not_met_count(self) -> int:
        return sum(1 for e in self.criterion_evaluations if e.status == CriterionStatus.NOT_MET)

    @property
    def criteria_undetermined_count(self) -> int:
        return sum(1 for e in self.criterion_evaluations if e.status == CriterionStatus.UNDETERMINED)

    @property
    def all_citations(self) -> list[EvidenceCitation]:
        return [c for e in self.criterion_evaluations for c in e.evidence_citations]


# ---------------------------------------------------------------------------
# Guardrail models
# ---------------------------------------------------------------------------

@dataclass
class GuardrailViolation:
    """A single violation detected by a guardrail check."""
    violation_type:  ViolationType
    severity:        ViolationSeverity
    message:         str
    details:         dict[str, Any] = field(default_factory=dict)
    criterion_id:    str | None = None


@dataclass
class GuardrailResult:
    """Aggregate result from running one or more guardrail checks."""
    passed:          bool
    violations:      list[GuardrailViolation] = field(default_factory=list)
    corrected_output: dict[str, Any] | None = None
    guardrail_name:  str = "unknown"
    latency_ms:      float = 0.0

    @property
    def has_critical(self) -> bool:
        return any(v.severity == ViolationSeverity.CRITICAL for v in self.violations)

    @property
    def has_high(self) -> bool:
        return any(v.severity == ViolationSeverity.HIGH for v in self.violations)

    @property
    def escalation_triggers(self) -> set[EscalationTrigger]:
        """Map violations to escalation triggers."""
        mapping = {
            ViolationType.SCHEMA_INVALID:         EscalationTrigger.SCHEMA_FAILURE,
            ViolationType.HALLUCINATION:          EscalationTrigger.HALLUCINATION_DETECTED,
            ViolationType.GROUNDEDNESS_FAILURE:   EscalationTrigger.GROUNDEDNESS_WEAK,
            ViolationType.LOW_CONFIDENCE:         EscalationTrigger.LOW_CONFIDENCE,
            ViolationType.EVIDENCE_MISSING:       EscalationTrigger.EVIDENCE_MISSING,
            ViolationType.UNSAFE_CONTENT:         EscalationTrigger.UNSAFE_OUTPUT,
            ViolationType.TIMEOUT:                EscalationTrigger.TIMEOUT,
            ViolationType.PROVIDER_ERROR:         EscalationTrigger.PROVIDER_FAILURE,
        }
        return {
            mapping[v.violation_type]
            for v in self.violations
            if v.violation_type in mapping
        }


# ---------------------------------------------------------------------------
# Attempt tracking
# ---------------------------------------------------------------------------

@dataclass
class ReasoningAttempt:
    """Record of one LLM call attempt within the orchestration loop."""
    attempt_number:   int
    model_tier:       ModelTier
    model_id:         str
    raw_output:       str | None
    parsed_output:    ReasoningOutput | None
    guardrail_result: GuardrailResult | None
    error:            str | None
    latency_ms:       float
    prompt_tokens:    int
    completion_tokens: int
    escalation_trigger: EscalationTrigger | None = None
    timestamp:        datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def succeeded(self) -> bool:
        return (
            self.parsed_output is not None
            and self.guardrail_result is not None
            and self.guardrail_result.passed
        )


@dataclass
class ReasoningResult:
    """Final result from the multi-model orchestration loop."""
    output:              ReasoningOutput | None
    attempts:            list[ReasoningAttempt]
    final_tier:          ModelTier
    escalations_count:   int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_latency_ms:    float
    requires_human_escalation: bool = False
    escalation_reason:   str | None = None
    guardrail_violations: list[GuardrailViolation] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.output is not None and not self.requires_human_escalation

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens

    @property
    def estimated_cost_usd(self) -> float:
        config = MODEL_TIER_MAP.get(self.final_tier, MEDIUM_MODEL_CONFIG)
        return (
            self.total_prompt_tokens / 1000 * config.cost_per_1k_prompt
            + self.total_completion_tokens / 1000 * config.cost_per_1k_completion
        )
