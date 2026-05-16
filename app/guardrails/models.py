"""
Guardrail framework data models.

All guardrail detectors return GuardrailViolation objects collected into
a GuardrailResult.  The pipeline inspects the result to decide whether to
block the request, sanitize the content, or escalate to a human reviewer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ViolationType(str, Enum):
    PROMPT_INJECTION         = "prompt_injection"
    JAILBREAK                = "jailbreak"
    RETRIEVAL_POISONING      = "retrieval_poisoning"
    PII_LEAKAGE              = "pii_leakage"
    UNSAFE_OUTPUT            = "unsafe_output"
    POLICY_GROUNDING_FAILURE = "policy_grounding_failure"
    SCHEMA_VIOLATION         = "schema_violation"
    TOOL_ABUSE               = "tool_abuse"
    OUTPUT_MODERATION        = "output_moderation"
    EVALUATOR_SAFETY         = "evaluator_safety"


class ViolationSeverity(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"

    @property
    def numeric(self) -> int:
        return {"low": 1, "medium": 2, "high": 3, "critical": 4}[self.value]

    def __ge__(self, other: "ViolationSeverity") -> bool:
        return self.numeric >= other.numeric

    def __gt__(self, other: "ViolationSeverity") -> bool:
        return self.numeric > other.numeric


class GuardrailStage(str, Enum):
    PRE_RETRIEVAL  = "pre_retrieval"   # Before vector DB lookup
    PRE_LLM        = "pre_llm"         # After retrieval, before LLM call
    POST_LLM       = "post_llm"        # After LLM response, before return
    TOOL_EXECUTION = "tool_execution"  # Around tool/function calls
    HTTP_REQUEST   = "http_request"    # HTTP middleware layer


@dataclass
class GuardrailViolation:
    """One detected guardrail violation."""

    violation_type: ViolationType
    severity:       ViolationSeverity
    description:    str
    confidence:     float                    # 0.0–1.0
    evidence:       dict[str, Any] = field(default_factory=dict)
    stage:          GuardrailStage = GuardrailStage.PRE_LLM
    detector:       str = ""                 # Name of the detector that fired
    violation_id:   str = field(default_factory=lambda: str(uuid.uuid4()))
    detected_at:    datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "violation_id":    self.violation_id,
            "violation_type":  self.violation_type.value,
            "severity":        self.severity.value,
            "description":     self.description,
            "confidence":      round(self.confidence, 4),
            "stage":           self.stage.value,
            "detector":        self.detector,
            "detected_at":     self.detected_at.isoformat(),
            "evidence":        self.evidence,
        }


@dataclass
class GuardrailResult:
    """
    Aggregated result from running one or more guardrail detectors.

    Attributes
    ----------
    passed:            True when no blocking violations were found.
    blocked:           True when the request/response must be rejected.
    escalated:         True when a human reviewer must be notified.
    violations:        All detected violations (blocking and non-blocking).
    sanitized_content: Cleaned content when the pipeline sanitized rather than blocked.
    stage:             Which pipeline stage produced this result.
    processing_ms:     Wall-clock time the full guardrail check took.
    case_id:           Linked PA case (for audit correlation).
    """

    passed:            bool
    blocked:           bool = False
    escalated:         bool = False
    violations:        list[GuardrailViolation] = field(default_factory=list)
    sanitized_content: str | None = None
    stage:             GuardrailStage = GuardrailStage.PRE_LLM
    processing_ms:     float = 0.0
    case_id:           str | None = None
    node_name:         str | None = None
    result_id:         str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at:        datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def max_severity(self) -> ViolationSeverity | None:
        if not self.violations:
            return None
        return max(v.severity for v in self.violations, key=lambda s: s.numeric)

    @property
    def blocking_violations(self) -> list[GuardrailViolation]:
        return [v for v in self.violations if v.severity >= ViolationSeverity.HIGH]

    @property
    def violation_types(self) -> list[ViolationType]:
        return list({v.violation_type for v in self.violations})

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id":         self.result_id,
            "passed":            self.passed,
            "blocked":           self.blocked,
            "escalated":         self.escalated,
            "stage":             self.stage.value,
            "processing_ms":     round(self.processing_ms, 1),
            "violation_count":   len(self.violations),
            "max_severity":      self.max_severity.value if self.max_severity else None,
            "violation_types":   [v.value for v in self.violation_types],
            "violations":        [v.to_dict() for v in self.violations],
            "has_sanitized":     self.sanitized_content is not None,
        }

    @classmethod
    def clean(
        cls,
        stage: GuardrailStage = GuardrailStage.PRE_LLM,
        processing_ms: float = 0.0,
    ) -> "GuardrailResult":
        """Convenience factory for a clean pass result."""
        return cls(passed=True, stage=stage, processing_ms=processing_ms)

    @classmethod
    def block(
        cls,
        violations: list[GuardrailViolation],
        stage: GuardrailStage = GuardrailStage.PRE_LLM,
        processing_ms: float = 0.0,
    ) -> "GuardrailResult":
        """Convenience factory for a blocked result."""
        return cls(
            passed=False,
            blocked=True,
            violations=violations,
            stage=stage,
            processing_ms=processing_ms,
        )


@dataclass
class EscalationEvent:
    """Represents a security escalation triggered by guardrail violations."""

    escalation_id:  str = field(default_factory=lambda: str(uuid.uuid4()))
    case_id:        str | None = None
    violations:     list[GuardrailViolation] = field(default_factory=list)
    escalated_to:   str = "reviewer"        # "reviewer" | "admin" | "security"
    reason:         str = ""
    auto_blocked:   bool = False
    created_at:     datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved:       bool = False
    resolved_by:    str | None = None
    resolved_at:    datetime | None = None
