"""
Domain enums for the PA Review Platform.

All enums use `str` as a mixin so they serialize to plain strings in JSON
responses and SQLAlchemy Enum columns without extra mapping.

Convention: SCREAMING_SNAKE_CASE values match the MySQL ENUM literals
stored in the database, ensuring round-trip safety.
"""

from __future__ import annotations

from enum import Enum


# ----------------------------------------------------------
# PA Case
# ----------------------------------------------------------

class CaseStatus(str, Enum):
    """Lifecycle states of a prior authorization case."""
    SUBMITTED             = "SUBMITTED"             # Received, not yet processed
    PROCESSING            = "PROCESSING"            # OCR / extraction in progress
    PENDING_CLARIFICATION = "PENDING_CLARIFICATION" # Waiting on provider response
    UNDER_REVIEW          = "UNDER_REVIEW"          # Assigned to a human reviewer
    APPROVED              = "APPROVED"              # Final: approved
    DENIED                = "DENIED"                # Final: denied
    PENDED                = "PENDED"                # Deferred — needs more information
    ESCALATED             = "ESCALATED"             # Sent to senior reviewer
    CANCELLED             = "CANCELLED"             # Withdrawn by submitter


class CasePriority(str, Enum):
    """Clinical urgency level — affects queue ordering."""
    ROUTINE   = "ROUTINE"
    URGENT    = "URGENT"
    EMERGENT  = "EMERGENT"


class ServiceType(str, Enum):
    """Broad category of the requested service."""
    IMAGING                    = "IMAGING"
    LABORATORY                 = "LABORATORY"
    DURABLE_MEDICAL_EQUIPMENT  = "DURABLE_MEDICAL_EQUIPMENT"
    MEDICATION                 = "MEDICATION"
    PROCEDURE                  = "PROCEDURE"
    SPECIALTY_REFERRAL         = "SPECIALTY_REFERRAL"
    HOME_HEALTH                = "HOME_HEALTH"
    INPATIENT_ADMISSION        = "INPATIENT_ADMISSION"
    OUTPATIENT_SURGERY         = "OUTPATIENT_SURGERY"
    BEHAVIORAL_HEALTH          = "BEHAVIORAL_HEALTH"
    OTHER                      = "OTHER"


# ----------------------------------------------------------
# Documents
# ----------------------------------------------------------

class DocumentType(str, Enum):
    """Type of uploaded clinical document."""
    PRESCRIPTION               = "PRESCRIPTION"
    LAB_REPORT                 = "LAB_REPORT"
    MEDICAL_NECESSITY          = "MEDICAL_NECESSITY"
    REFERRAL                   = "REFERRAL"
    EHR_EXPORT                 = "EHR_EXPORT"
    IMAGING_REPORT             = "IMAGING_REPORT"
    CLINICAL_NOTES             = "CLINICAL_NOTES"
    PRIOR_AUTH_REQUEST_FORM    = "PRIOR_AUTH_REQUEST_FORM"
    INSURANCE_CARD             = "INSURANCE_CARD"
    APPEAL                     = "APPEAL"
    FAX                        = "FAX"
    OTHER                      = "OTHER"


class OCRProvider(str, Enum):
    """Which OCR engine processed the document."""
    AZURE      = "AZURE"       # Azure AI Document Intelligence (primary)
    PADDLEOCR  = "PADDLEOCR"   # PaddleOCR (fallback)
    NONE       = "NONE"        # No OCR needed (e.g., structured JSON)


class OCRStatus(str, Enum):
    """Processing state of the OCR pipeline for a document."""
    PENDING       = "PENDING"
    PROCESSING    = "PROCESSING"
    COMPLETED     = "COMPLETED"
    FAILED        = "FAILED"
    FALLBACK_USED = "FALLBACK_USED"  # Azure failed → PaddleOCR succeeded


# ----------------------------------------------------------
# Extracted Entities
# ----------------------------------------------------------

class EntityType(str, Enum):
    """Category of a medical entity extracted from a document."""
    PATIENT_DEMOGRAPHICS = "PATIENT_DEMOGRAPHICS"
    PROVIDER_INFO        = "PROVIDER_INFO"
    DIAGNOSIS_CODE       = "DIAGNOSIS_CODE"       # ICD code
    PROCEDURE_CODE       = "PROCEDURE_CODE"       # CPT code
    MEDICATION           = "MEDICATION"
    LAB_VALUE            = "LAB_VALUE"
    GLUCOSE_READING      = "GLUCOSE_READING"
    INSULIN_FREQUENCY    = "INSULIN_FREQUENCY"
    TREATMENT_HISTORY    = "TREATMENT_HISTORY"
    COMPLICATION         = "COMPLICATION"
    SYMPTOM              = "SYMPTOM"
    DATE_OF_SERVICE      = "DATE_OF_SERVICE"
    INSURANCE_INFO       = "INSURANCE_INFO"
    OTHER                = "OTHER"


class ExtractionMethod(str, Enum):
    """How an entity was extracted."""
    LLM    = "LLM"     # Large language model extraction
    OCR    = "OCR"     # Direct OCR text match
    REGEX  = "REGEX"   # Regular expression pattern
    MANUAL = "MANUAL"  # Entered by a human reviewer


# ----------------------------------------------------------
# AI Evaluations
# ----------------------------------------------------------

class EvaluationType(str, Enum):
    """Whether this evaluation came from AI or a human."""
    AI_CRITERION = "AI_CRITERION"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class CriterionStatus(str, Enum):
    """Outcome of evaluating a single policy criterion against patient evidence."""
    PASS                 = "PASS"
    FAIL                 = "FAIL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_APPLICABLE       = "NOT_APPLICABLE"


# ----------------------------------------------------------
# Clarification Loop
# ----------------------------------------------------------

class ClarificationStatus(str, Enum):
    """State of a clarification request sent to the provider."""
    PENDING   = "PENDING"    # Sent, awaiting response
    ANSWERED  = "ANSWERED"   # Provider responded
    TIMEOUT   = "TIMEOUT"    # No response within SLA
    ESCALATED = "ESCALATED"  # Max attempts reached → escalated


# ----------------------------------------------------------
# Human Review
# ----------------------------------------------------------

class ReviewerActionType(str, Enum):
    """Type of action taken by a clinical reviewer."""
    ASSIGNED               = "ASSIGNED"
    VIEWED                 = "VIEWED"
    APPROVED               = "APPROVED"
    DENIED                 = "DENIED"
    PENDED                 = "PENDED"
    OVERRIDE_APPROVED      = "OVERRIDE_APPROVED"   # Overrode AI DENY → APPROVE
    OVERRIDE_DENIED        = "OVERRIDE_DENIED"     # Overrode AI APPROVE → DENY
    REQUESTED_CLARIFICATION = "REQUESTED_CLARIFICATION"
    ESCALATED              = "ESCALATED"
    ADDED_NOTE             = "ADDED_NOTE"


# ----------------------------------------------------------
# Decision
# ----------------------------------------------------------

class DecisionOutcome(str, Enum):
    """Final prior authorization decision outcomes."""
    APPROVE = "APPROVE"
    DENY    = "DENY"
    PEND    = "PEND"


class DecisionSource(str, Enum):
    """Whether the final decision came from AI or a reviewer override."""
    AI_RECOMMENDATION = "AI_RECOMMENDATION"
    REVIEWER_OVERRIDE = "REVIEWER_OVERRIDE"


# ----------------------------------------------------------
# Audit
# ----------------------------------------------------------

class AuditAction(str, Enum):
    """Type of action recorded in the audit trail."""
    CREATE        = "CREATE"
    READ          = "READ"
    UPDATE        = "UPDATE"
    DELETE        = "DELETE"
    STATUS_CHANGE = "STATUS_CHANGE"
    LOGIN         = "LOGIN"
    LOGOUT        = "LOGOUT"
    EXPORT        = "EXPORT"
    AI_INFERENCE  = "AI_INFERENCE"
    OCR_PROCESSED = "OCR_PROCESSED"
    DECISION_MADE = "DECISION_MADE"
    OVERRIDE      = "OVERRIDE"


class ActorType(str, Enum):
    """Who (or what) performed an audited action."""
    USER   = "USER"    # Human user (reviewer, admin, provider)
    SYSTEM = "SYSTEM"  # Internal automated process
    AI     = "AI"      # LLM / AI reasoning engine


class AuditEntityType(str, Enum):
    """Which domain entity type an audit log entry references."""
    PATIENT         = "PATIENT"
    PROVIDER        = "PROVIDER"
    PA_CASE         = "PA_CASE"
    DOCUMENT        = "DOCUMENT"
    EVALUATION      = "EVALUATION"
    CLARIFICATION   = "CLARIFICATION"
    REVIEWER_ACTION = "REVIEWER_ACTION"
    DECISION        = "DECISION"
    POLICY_MATCH    = "POLICY_MATCH"
    USER            = "USER"
    SYSTEM          = "SYSTEM"


# ----------------------------------------------------------
# Provider
# ----------------------------------------------------------

class ProviderType(str, Enum):
    """Whether the provider is an individual practitioner or an organization."""
    INDIVIDUAL   = "INDIVIDUAL"
    ORGANIZATION = "ORGANIZATION"


# ----------------------------------------------------------
# Metric
# ----------------------------------------------------------

class MetricType(str, Enum):
    """Prometheus-style metric type for business KPI records."""
    COUNTER   = "COUNTER"
    GAUGE     = "GAUGE"
    HISTOGRAM = "HISTOGRAM"
    SUMMARY   = "SUMMARY"
