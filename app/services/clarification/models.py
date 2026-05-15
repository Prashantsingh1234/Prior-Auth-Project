"""
Data models for the clarification loop system.

These are internal to the clarification service.  The workflow state
continues to use ClarificationAttempt from state/models.py — these models
represent the richer internal objects used during question generation,
response processing, and escalation decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MissingInfoCategory(str, Enum):
    """Clinical domain of the missing information."""
    LAB_RESULT             = "lab_result"          # HbA1c, glucose, labs
    TREATMENT_HISTORY      = "treatment_history"   # Prior drugs, duration, failures
    CLINICAL_DIAGNOSIS     = "clinical_diagnosis"  # Diagnosis confirmation
    CLINICAL_MEASUREMENT   = "clinical_measurement" # BMI, weight, BP
    PROVIDER_ATTESTATION   = "provider_attestation" # Physician attestation
    PRIOR_AUTHORIZATION    = "prior_authorization"  # Prior PA history
    INSURANCE_ELIGIBILITY  = "insurance_eligibility"
    PROCEDURE_INDICATION   = "procedure_indication" # Why this procedure
    CONTRAINDICATION_CHECK = "contraindication_check"
    DURATION               = "duration"            # How long on therapy
    DATES                  = "dates"               # Onset date, last visit
    OTHER                  = "other"


class QuestionPriority(str, Enum):
    CRITICAL = "critical"  # Without this, evaluation cannot proceed
    HIGH     = "high"      # Strongly affects recommendation
    MEDIUM   = "medium"    # Useful but not blocking
    LOW      = "low"       # Nice-to-have context


class ResponseQualityLevel(str, Enum):
    SUFFICIENT     = "sufficient"   # Addresses the question completely
    PARTIAL        = "partial"      # Partially addresses; usable but not ideal
    INSUFFICIENT   = "insufficient" # Does not address the question
    UNRELATED      = "unrelated"    # Appears unrelated to the question


class EscalationReason(str, Enum):
    MAX_ATTEMPTS_REACHED    = "max_attempts_reached"
    TIMEOUT                 = "timeout"
    INSUFFICIENT_RESPONSE   = "insufficient_response"
    REPEATED_SAME_QUESTION  = "repeated_same_question"
    PROVIDER_NON_RESPONSIVE = "provider_non_responsive"
    CLINICAL_COMPLEXITY     = "clinical_complexity"
    POLICY_AMBIGUITY        = "policy_ambiguity"
    SYSTEM_ERROR            = "system_error"


class NotificationEvent(str, Enum):
    CLARIFICATION_SENT      = "clarification_sent"
    CLARIFICATION_ANSWERED  = "clarification_answered"
    CLARIFICATION_TIMEOUT   = "clarification_timeout"
    MAX_ATTEMPTS_REACHED    = "max_attempts_reached"
    ESCALATED_TO_REVIEWER   = "escalated_to_reviewer"


# ---------------------------------------------------------------------------
# Missing information analysis
# ---------------------------------------------------------------------------

@dataclass
class MissingInfoItem:
    """One piece of missing information identified from evaluation results."""
    item_id:         str = field(default_factory=lambda: str(uuid4()))
    category:        MissingInfoCategory = MissingInfoCategory.OTHER
    priority:        QuestionPriority = QuestionPriority.MEDIUM
    description:     str = ""
    affected_criteria: list[str] = field(default_factory=list)  # criterion_ids
    specific_value_needed: str = ""  # e.g., "HbA1c value from last 3 months"
    context:         str = ""        # relevant excerpt from clinical summary
    already_asked:   bool = False    # True if a previous attempt covered this


@dataclass
class MissingInfoAnalysis:
    """Full analysis of missing information gaps in an evaluation."""
    case_id:          str
    items:            list[MissingInfoItem] = field(default_factory=list)
    total_undetermined: int = 0
    critical_count:   int = 0
    has_prior_attempts: bool = False
    prior_questions:  list[str] = field(default_factory=list)
    analyzed_at:      datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def prioritized_items(self) -> list[MissingInfoItem]:
        """Return items sorted by priority (CRITICAL first) excluding already-asked."""
        order = {
            QuestionPriority.CRITICAL: 0,
            QuestionPriority.HIGH: 1,
            QuestionPriority.MEDIUM: 2,
            QuestionPriority.LOW: 3,
        }
        return sorted(
            [i for i in self.items if not i.already_asked],
            key=lambda x: order.get(x.priority, 9),
        )

    @property
    def actionable_items(self) -> list[MissingInfoItem]:
        """Items that can still be asked about (not already covered)."""
        return [i for i in self.items if not i.already_asked]


# ---------------------------------------------------------------------------
# Clarification request (generated question)
# ---------------------------------------------------------------------------

@dataclass
class ClarificationRequest:
    """
    A generated clarification question ready to be sent to the provider.

    Created by ClarificationQuestionGenerator and persisted as a
    ClarificationAttempt in the workflow state.
    """
    request_id:       str = field(default_factory=lambda: str(uuid4()))
    question:         str = ""
    question_category: str = MissingInfoCategory.OTHER.value
    addressed_items:  list[MissingInfoItem] = field(default_factory=list)
    missing_criteria: list[str] = field(default_factory=list)  # criterion_ids
    priority:         QuestionPriority = QuestionPriority.HIGH
    deadline:         datetime | None = None
    context_summary:  str = ""        # brief context for the provider
    generated_by:     str = "llm"     # "llm" | "template"
    generation_model: str = ""
    tokens_used:      int = 0
    generated_at:     datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def with_deadline(
        cls, hours: int = 48, **kwargs
    ) -> "ClarificationRequest":
        return cls(
            deadline=datetime.now(UTC) + timedelta(hours=hours),
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Clarification response (received answer)
# ---------------------------------------------------------------------------

@dataclass
class ClarificationResponse:
    """
    A received response to a clarification question, after processing.

    Includes quality assessment and any extracted clinical entities.
    """
    attempt_id:       str
    response_text:    str
    responded_by:     str = "provider"
    response_quality: ResponseQualityLevel = ResponseQualityLevel.SUFFICIENT
    quality_score:    float = 1.0   # 0.0–1.0
    extracted_info:   dict[str, Any] = field(default_factory=dict)
    addresses_question: bool = True
    follow_up_needed: bool = False
    follow_up_reason: str = ""
    processed_at:     datetime = field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------

@dataclass
class ClarificationEscalationDecision:
    """
    Decision about whether to escalate after a clarification cycle.

    is_escalate: True → send to human reviewer
    reason:      Why escalation was triggered
    context:     Additional metadata for the reviewer
    """
    is_escalate:     bool
    reason:          EscalationReason | None = None
    message:         str = ""
    context:         dict[str, Any] = field(default_factory=dict)
    notify_reviewer: bool = True


# ---------------------------------------------------------------------------
# Notification payload
# ---------------------------------------------------------------------------

@dataclass
class NotificationPayload:
    """Event payload sent to reviewer notification hooks."""
    event:       NotificationEvent
    case_id:     str
    attempt_id:  str | None = None
    attempt_number: int = 0
    question:    str = ""
    response:    str | None = None
    reason:      str | None = None
    metadata:    dict[str, Any] = field(default_factory=dict)
    timestamp:   datetime = field(default_factory=lambda: datetime.now(UTC))
