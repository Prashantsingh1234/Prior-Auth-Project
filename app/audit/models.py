"""
Healthcare-grade audit logging models.

All 9 auditable domains:
  1. API_REQUEST     — HTTP method, path, status, latency, client identity
  2. OCR             — document provider, confidence, pages, fallback
  3. EXTRACTION      — entities extracted, model, confidence, tokens
  4. RETRIEVAL       — policy query, chunks, scores, strategy
  5. LLM_CALL        — model tier, operation, tokens, latency, outcome
  6. REVIEWER_ACTION — reviewer identity, action type, override reason
  7. DECISION        — verdict, rule, confidence, review routing
  8. CLARIFICATION   — attempt number, category, response quality
  9. ERROR           — component, error type, message, hashed stack trace

Design:
  - AuditRecord is the canonical transfer object between event factories,
    the writer, and storage backends.
  - content_hash (SHA-256) over key fields enables tamper detection.
  - log_data is a PII-masked version for structured log sinks.
  - event_data is the full-fidelity payload persisted to the database.
  - Every record carries a full AuditContext (tracing IDs, actor, IP).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AuditCategory(str, Enum):
    """The 9 auditable domains in the PA platform."""
    API_REQUEST      = "api_request"
    OCR              = "ocr"
    EXTRACTION       = "extraction"
    RETRIEVAL        = "retrieval"
    LLM_CALL         = "llm_call"
    REVIEWER_ACTION  = "reviewer_action"
    DECISION         = "decision"
    CLARIFICATION    = "clarification"
    ERROR            = "error"


class AuditSeverity(str, Enum):
    DEBUG    = "debug"
    INFO     = "info"
    WARNING  = "warning"
    ERROR    = "error"
    CRITICAL = "critical"


class AuditActorType(str, Enum):
    SYSTEM            = "system"      # Internal automated process
    USER              = "user"        # Human user (provider portal, admin)
    REVIEWER          = "reviewer"    # Clinical reviewer
    AI                = "ai"          # LLM / reasoning engine
    API_CLIENT        = "api_client"  # External API consumer
    EXTERNAL_SERVICE  = "external_service"  # OCR provider, webhook


# ---------------------------------------------------------------------------
# Audit context (threaded via contextvars — see context.py)
# ---------------------------------------------------------------------------

@dataclass
class AuditContext:
    """
    Cross-cutting tracing context threaded through every audit record.

    Set once per HTTP request by AuditMiddleware; propagated automatically
    through async boundaries via contextvars.
    """
    request_id:    str | None = None
    trace_id:      str | None = None
    session_id:    str | None = None
    user_id:       str | None = None
    actor_type:    AuditActorType = AuditActorType.SYSTEM
    actor_name:    str | None = None
    actor_ip:      str | None = None
    actor_user_agent: str | None = None
    case_id:       str | None = None    # May be set later in the request lifecycle

    def with_case(self, case_id: str) -> "AuditContext":
        """Return a copy with case_id set."""
        from dataclasses import replace
        return replace(self, case_id=case_id)


# ---------------------------------------------------------------------------
# Core audit record
# ---------------------------------------------------------------------------

@dataclass
class AuditRecord:
    """
    Canonical transfer object for the audit system.

    Produced by event factory functions, queued by AuditWriter,
    and consumed by storage backends.
    """
    # Identity
    event_id:     str = field(default_factory=lambda: str(uuid4()))
    category:     AuditCategory = AuditCategory.ERROR
    action:       str = ""           # Verb: "document.ocr.processed", "policy.retrieved", etc.
    severity:     AuditSeverity = AuditSeverity.INFO

    # Tracing context
    audit_ctx:    AuditContext = field(default_factory=AuditContext)

    # Domain context
    case_id:      str | None = None  # Denormalized from audit_ctx for indexed lookups
    document_id:  str | None = None
    policy_id:    str | None = None
    attempt_id:   str | None = None  # Clarification attempt

    # Payload
    event_data:   dict[str, Any] = field(default_factory=dict)   # Full fidelity (DB)
    log_data:     dict[str, Any] = field(default_factory=dict)   # PII-masked (log sinks)

    # State snapshots for forensic analysis
    previous_state: dict[str, Any] | None = None
    new_state:      dict[str, Any] | None = None
    changed_fields: list[str] = field(default_factory=list)

    # Timing
    occurred_at:  datetime = field(default_factory=lambda: datetime.now(UTC))
    duration_ms:  float | None = None

    # Error fields (populated for ERROR category)
    error_type:    str | None = None
    error_message: str | None = None
    error_hash:    str | None = None   # SHA-256 of stack trace (PII-safe)

    # Tamper-evidence
    content_hash: str = field(default="")   # Computed in __post_init__

    def __post_init__(self) -> None:
        # Propagate case_id from context if not explicitly set
        if self.case_id is None and self.audit_ctx.case_id:
            self.case_id = self.audit_ctx.case_id
        # Compute tamper-evidence hash after all fields are set
        if not self.content_hash:
            self.content_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """
        SHA-256 over identity + tracing + payload fields.

        Allows downstream verification that the record hasn't been altered
        after the hash was computed. Does NOT include content_hash itself.
        """
        components = "|".join([
            self.event_id,
            self.category.value,
            self.action,
            self.case_id or "",
            self.audit_ctx.user_id or "",
            self.audit_ctx.request_id or "",
            self.occurred_at.isoformat(),
            _stable_json(self.event_data),
        ])
        return hashlib.sha256(components.encode("utf-8")).hexdigest()

    def verify(self) -> bool:
        """Return True if the record's content_hash matches the recomputed hash."""
        return self.content_hash == self._compute_hash()

    def to_log_dict(self) -> dict[str, Any]:
        """Flatten into a structlog-compatible dict (uses PII-masked log_data)."""
        return {
            "audit.event_id":    self.event_id,
            "audit.category":    self.category.value,
            "audit.action":      self.action,
            "audit.severity":    self.severity.value,
            "audit.case_id":     self.case_id,
            "audit.document_id": self.document_id,
            "audit.policy_id":   self.policy_id,
            "audit.actor_type":  self.audit_ctx.actor_type.value,
            "audit.actor_id":    self.audit_ctx.user_id,
            "audit.request_id":  self.audit_ctx.request_id,
            "audit.trace_id":    self.audit_ctx.trace_id,
            "audit.occurred_at": self.occurred_at.isoformat(),
            "audit.duration_ms": self.duration_ms,
            "audit.content_hash": self.content_hash,
            **{f"audit.{k}": v for k, v in self.log_data.items()},
        }


# ---------------------------------------------------------------------------
# Typed event_data TypedDicts (documentation / IDE support)
# ---------------------------------------------------------------------------

# These are not enforced at runtime — they document the contract for each
# audit category's event_data payload.

class ApiRequestData(dict):
    """Keys: method, path, status_code, duration_ms, query_params_hash"""

class OcrEventData(dict):
    """Keys: provider, confidence, page_count, duration_ms, fallback_used, document_type"""

class ExtractionEventData(dict):
    """Keys: document_id, entities_count, confidence, model, tokens_used, entity_breakdown"""

class RetrievalEventData(dict):
    """Keys: query_hash, policies_found, top_score, strategy, chunks_returned, latency_ms"""

class LlmCallEventData(dict):
    """Keys: model, tier, operation, prompt_tokens, completion_tokens, latency_ms, outcome"""

class ReviewerActionEventData(dict):
    """Keys: reviewer_id, action_type, override_reason_hash, duration_seconds, ai_verdict_at_time"""

class DecisionEventData(dict):
    """Keys: verdict, rule_applied, confidence, requires_review, review_reason, policies_evaluated"""

class ClarificationEventData(dict):
    """Keys: attempt_number, category, question_hash, response_quality, generated_by"""

class ErrorEventData(dict):
    """Keys: component, error_type, error_message, error_hash, is_retriable"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stable_json(data: dict[str, Any]) -> str:
    """Produce stable JSON for hashing (sorted keys, no whitespace)."""
    try:
        return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        return str(data)


def hash_sensitive(text: str) -> str:
    """One-way hash of sensitive text (stack traces, PII) for safe logging."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def mask_member_id(member_id: str | None) -> str | None:
    """Partially mask a member ID: show last 4 chars only."""
    if not member_id:
        return None
    if len(member_id) <= 4:
        return "****"
    return "****" + member_id[-4:]
