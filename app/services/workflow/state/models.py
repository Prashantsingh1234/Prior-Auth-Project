"""
LangGraph workflow state domain models.

Each model represents one logical field in PAWorkflowState.
All models are Pydantic v2, JSON-serializable, and immutable-safe
(model_copy(update={...}) is the only mutation pattern).

Import hierarchy:
  models.py  ← no internal deps (can import from extraction.models)
  reducers.py ← imports models
  schema.py   ← imports models + reducers
  mutations.py ← imports schema + audit
  audit.py    ← imports models
"""

from __future__ import annotations

import operator
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.services.extraction.models import (
    Complication,
    Diagnosis,
    GlucoseReading,
    HbA1cReading,
    InsulinRegimen,
    LabValue,
    Medication,
    PatientDemographics,
    ProviderDetails,
    Symptom,
    TreatmentHistory,
    ValidatedCode,
)


# ---------------------------------------------------------------------------
# Workflow lifecycle
# ---------------------------------------------------------------------------

class WorkflowPhase(str, Enum):
    INGESTION       = "ingestion"       # Receiving + parsing documents
    EXTRACTION      = "extraction"      # Extracting medical entities
    RETRIEVAL       = "retrieval"       # Fetching matching policy criteria
    EVALUATION      = "evaluation"      # Evaluating criteria against evidence
    CLARIFICATION   = "clarification"   # Requesting missing information
    RECOMMENDATION  = "recommendation"  # Generating AI decision
    HUMAN_REVIEW    = "human_review"    # Awaiting reviewer action
    COMPLETED       = "completed"       # Terminal — final decision recorded
    FAILED          = "failed"          # Terminal — unrecoverable error


# ---------------------------------------------------------------------------
# Raw document
# ---------------------------------------------------------------------------

class DocumentStatus(str, Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    PROCESSED  = "processed"
    FAILED     = "failed"


class RawDocument(BaseModel):
    """
    A document submitted as part of a PA request.

    content is bytes (base64-encoded when serialized). For large documents
    prefer content_text after extraction; keep content only for reprocessing.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    document_id:  str           = Field(default_factory=lambda: str(uuid4()))
    filename:     str | None    = None
    mime_type:    str           = "application/octet-stream"
    document_type: str          = "unknown"         # DocumentType.value
    content:      bytes | None  = None              # Raw bytes (not persisted in state)
    content_text: str | None    = None              # Extracted plain text
    page_count:   int           = 0
    file_size:    int           = 0                 # bytes
    sha256_hash:  str | None    = None
    status:       DocumentStatus = DocumentStatus.PENDING
    received_at:  datetime      = Field(default_factory=datetime.utcnow)
    processed_at: datetime | None = None
    error:        str | None    = None
    metadata:     dict[str, Any] = Field(default_factory=dict)

    def without_content(self) -> "RawDocument":
        """Return a copy with raw bytes cleared — safe for state storage."""
        return self.model_copy(update={"content": None})


# ---------------------------------------------------------------------------
# Extraction output
# ---------------------------------------------------------------------------

class ExtractedEntities(BaseModel):
    """
    Extraction output for a single document, stored in the workflow state.

    Wraps the key fields from ExtractionResult to avoid circular state growth
    while keeping full fidelity for downstream nodes.
    """
    document_id:      str
    patient:          PatientDemographics | None          = None
    provider:         ProviderDetails | None              = None
    diagnoses:        list[Diagnosis]                     = Field(default_factory=list)
    icd_codes:        list[ValidatedCode]                 = Field(default_factory=list)
    cpt_codes:        list[ValidatedCode]                 = Field(default_factory=list)
    medications:      list[Medication]                    = Field(default_factory=list)
    glucose_readings: list[GlucoseReading]                = Field(default_factory=list)
    hba1c_readings:   list[HbA1cReading]                  = Field(default_factory=list)
    insulin_regimens: list[InsulinRegimen]                = Field(default_factory=list)
    lab_values:       list[LabValue]                      = Field(default_factory=list)
    symptoms:         list[Symptom]                       = Field(default_factory=list)
    treatment_history: list[TreatmentHistory]             = Field(default_factory=list)
    complications:    list[Complication]                  = Field(default_factory=list)
    overall_confidence: float                             = 0.0
    grounding_pass_rate: float                            = 0.0
    extraction_method: str                               = "unknown"
    llm_tokens_used:  int                                = 0
    extracted_at:     datetime                           = Field(default_factory=datetime.utcnow)

    @property
    def total_entities(self) -> int:
        return (
            len(self.diagnoses) + len(self.icd_codes) + len(self.cpt_codes)
            + len(self.medications) + len(self.glucose_readings)
            + len(self.hba1c_readings) + len(self.insulin_regimens)
            + len(self.lab_values) + len(self.symptoms)
            + len(self.treatment_history) + len(self.complications)
        )

    @property
    def primary_diagnosis(self) -> Diagnosis | None:
        for d in self.diagnoses:
            if d.is_primary:
                return d
        return self.diagnoses[0] if self.diagnoses else None


# ---------------------------------------------------------------------------
# Policy retrieval
# ---------------------------------------------------------------------------

class PolicyChunk(BaseModel):
    """A single policy criterion chunk from the vector store."""
    chunk_id:       str
    criterion_text: str
    criterion_type: str | None  = None   # CriterionType.value
    section_header: str | None  = None
    page_number:    int | None  = None
    similarity_score: float     = 0.0
    metadata:       dict[str, Any] = Field(default_factory=dict)


class RetrievedPolicy(BaseModel):
    """
    A policy document retrieved from Pinecone during the retrieval phase.

    Holds the top-K most relevant criterion chunks and the aggregate
    similarity score used for ranking.
    """
    policy_id:       str
    policy_version:  str                = "unknown"
    payer_name:      str | None         = None
    service_type:    str | None         = None
    cpt_codes:       list[str]          = Field(default_factory=list)
    icd_codes:       list[str]          = Field(default_factory=list)
    similarity_score: float             = 0.0
    criteria_chunks: list[PolicyChunk]  = Field(default_factory=list)
    retrieved_at:    datetime           = Field(default_factory=datetime.utcnow)
    retrieval_query: str | None         = None
    namespace:       str                = "policies"

    @property
    def total_criteria(self) -> int:
        return len(self.criteria_chunks)

    @property
    def dedup_key(self) -> str:
        return f"{self.policy_id}::{self.policy_version}"


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

class CriterionMet(str, Enum):
    YES           = "yes"
    NO            = "no"
    UNDETERMINED  = "undetermined"
    NOT_APPLICABLE = "not_applicable"


class CriterionEvaluation(BaseModel):
    """Evaluation of a single policy criterion against the clinical evidence."""
    criterion_id:    str
    criterion_text:  str
    criterion_type:  str | None  = None
    met:             CriterionMet = CriterionMet.UNDETERMINED
    confidence:      float        = 0.0
    evidence:        list[str]    = Field(default_factory=list)  # Supporting quotes
    policy_section:  str | None   = None
    notes:           str | None   = None
    requires_clarification: bool  = False


class EvaluationResult(BaseModel):
    """Evaluation of all criteria in a retrieved policy."""
    evaluation_id:      str             = Field(default_factory=lambda: str(uuid4()))
    policy_id:          str
    policy_version:     str
    criteria_evaluations: list[CriterionEvaluation] = Field(default_factory=list)
    overall_score:      float           = 0.0   # Fraction of criteria met
    criteria_met:       int             = 0
    criteria_not_met:   int             = 0
    criteria_undetermined: int          = 0
    criteria_total:     int             = 0
    evaluated_at:       datetime        = Field(default_factory=datetime.utcnow)
    model_used:         str | None      = None
    tokens_used:        int             = 0

    @property
    def dedup_key(self) -> str:
        return f"{self.policy_id}::{self.policy_version}"

    def model_post_init(self, __context: Any) -> None:
        self.criteria_total = len(self.criteria_evaluations)
        self.criteria_met = sum(
            1 for c in self.criteria_evaluations if c.met == CriterionMet.YES
        )
        self.criteria_not_met = sum(
            1 for c in self.criteria_evaluations if c.met == CriterionMet.NO
        )
        self.criteria_undetermined = sum(
            1 for c in self.criteria_evaluations
            if c.met == CriterionMet.UNDETERMINED
        )
        if self.criteria_total:
            self.overall_score = round(self.criteria_met / self.criteria_total, 4)


# ---------------------------------------------------------------------------
# Clarification
# ---------------------------------------------------------------------------

class ClarificationStatus(str, Enum):
    PENDING  = "pending"
    ANSWERED = "answered"
    TIMEOUT  = "timeout"
    SKIPPED  = "skipped"


class ClarificationAttempt(BaseModel):
    """One round of requesting additional information from the submitting provider."""
    attempt_id:        str               = Field(default_factory=lambda: str(uuid4()))
    attempt_number:    int               = 1
    question:          str
    question_category: str | None        = None  # e.g. "clinical_evidence", "prior_auth"
    missing_criteria:  list[str]         = Field(default_factory=list)
    asked_at:          datetime          = Field(default_factory=datetime.utcnow)
    deadline:          datetime | None   = None
    answered_at:       datetime | None   = None
    response:          str | None        = None
    responded_by:      str | None        = None   # "provider", "patient", "system"
    status:            ClarificationStatus = ClarificationStatus.PENDING


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------

class RecommendationType(str, Enum):
    APPROVE               = "approve"
    DENY                  = "deny"
    PEND_FOR_INFO         = "pend_for_info"
    REFER_MEDICAL_DIRECTOR = "refer_medical_director"


class PARecommendation(BaseModel):
    """
    AI-generated recommendation for a PA case.

    confidence_score: model's self-assessed certainty in [0, 1].
    requires_human_review: True whenever confidence < threshold or
      conflicting criteria exist — the graph enforces this flag.
    """
    recommendation_type:   RecommendationType
    confidence_score:      float              = 0.0
    rationale:             list[str]          = Field(default_factory=list)
    supporting_criteria:   list[str]          = Field(default_factory=list)
    conflicting_criteria:  list[str]          = Field(default_factory=list)
    evidence_references:   list[str]          = Field(default_factory=list)
    requires_human_review: bool               = False
    review_reason:         str | None         = None
    generated_at:          datetime           = Field(default_factory=datetime.utcnow)
    model_used:            str | None         = None
    tokens_used:           int                = 0

    @property
    def is_approval(self) -> bool:
        return self.recommendation_type == RecommendationType.APPROVE

    @property
    def is_denial(self) -> bool:
        return self.recommendation_type == RecommendationType.DENY

    @property
    def needs_info(self) -> bool:
        return self.recommendation_type == RecommendationType.PEND_FOR_INFO


# ---------------------------------------------------------------------------
# Reviewer actions
# ---------------------------------------------------------------------------

class ReviewerActionType(str, Enum):
    APPROVE              = "approve"
    DENY                 = "deny"
    PEND                 = "pend"
    OVERRIDE_APPROVE     = "override_approve"   # Overrides AI denial
    OVERRIDE_DENY        = "override_deny"      # Overrides AI approval
    REQUEST_CLARIFICATION = "request_clarification"
    ESCALATE             = "escalate"
    RETURN_FOR_REWORK    = "return_for_rework"


class ReviewerAction(BaseModel):
    """A human reviewer's action on a PA case."""
    action_id:                   str                    = Field(default_factory=lambda: str(uuid4()))
    reviewer_id:                 str
    reviewer_name:               str | None             = None
    action_type:                 ReviewerActionType
    timestamp:                   datetime               = Field(default_factory=datetime.utcnow)
    notes:                       str | None             = None
    override_reason:             str | None             = None
    ai_recommendation_at_time:   RecommendationType | None = None
    is_override:                 bool                   = False
    duration_seconds:            float | None           = None   # Time reviewer spent

    def model_post_init(self, __context: Any) -> None:
        self.is_override = self.action_type in (
            ReviewerActionType.OVERRIDE_APPROVE,
            ReviewerActionType.OVERRIDE_DENY,
        )


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

class AuditEventType(str, Enum):
    WORKFLOW_STARTED          = "workflow_started"
    DOCUMENT_RECEIVED         = "document_received"
    DOCUMENT_PARSED           = "document_parsed"
    ENTITIES_EXTRACTED        = "entities_extracted"
    POLICIES_RETRIEVED        = "policies_retrieved"
    CRITERIA_EVALUATED        = "criteria_evaluated"
    CLARIFICATION_SENT        = "clarification_sent"
    CLARIFICATION_RECEIVED    = "clarification_received"
    RECOMMENDATION_GENERATED  = "recommendation_generated"
    PHASE_TRANSITION          = "phase_transition"
    REVIEWER_ACTION           = "reviewer_action"
    WORKFLOW_COMPLETED        = "workflow_completed"
    WORKFLOW_FAILED           = "workflow_failed"
    STATE_CHECKPOINT          = "state_checkpoint"
    RETRY                     = "retry"
    ERROR                     = "error"


class AuditEvent(BaseModel):
    """
    Immutable audit log entry — one per node execution or significant state change.

    Append-only: the reducer never removes or mutates existing events.
    """
    event_id:    str            = Field(default_factory=lambda: str(uuid4()))
    event_type:  AuditEventType
    node_name:   str
    step:        int            = 0     # LangGraph step counter
    timestamp:   datetime       = Field(default_factory=datetime.utcnow)
    data:        dict[str, Any] = Field(default_factory=dict)
    duration_ms: float | None   = None
    error:       str | None     = None


class AuditMetadata(BaseModel):
    """
    Workflow-level metadata — single mutable record (last-write-wins in state).

    Updated by each node to accumulate totals. Does NOT contain the event log
    (that lives in audit_events to benefit from the append reducer).
    """
    created_at:        datetime              = Field(default_factory=datetime.utcnow)
    updated_at:        datetime              = Field(default_factory=datetime.utcnow)
    workflow_version:  str                   = "1.0"
    langsmith_run_id:  str | None            = None
    # Per-node timing registry (node_name → cumulative ms)
    node_timings:      dict[str, float]      = Field(default_factory=dict)
    # These mirror the Annotated[int/float, operator.add] fields in the schema
    # and are kept in sync by the workflow_completed node for reporting.
    total_tokens_used: int                   = 0
    total_processing_ms: float               = 0.0

    def record_node(self, node_name: str, duration_ms: float) -> "AuditMetadata":
        """Return updated copy with node timing recorded."""
        new_timings = dict(self.node_timings)
        new_timings[node_name] = new_timings.get(node_name, 0.0) + duration_ms
        return self.model_copy(update={
            "node_timings": new_timings,
            "updated_at": datetime.utcnow(),
        })
