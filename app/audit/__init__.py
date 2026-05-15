"""
Healthcare-grade audit logging system for the PA Review Platform.

Provides:
  - Immutable, HIPAA-compliant audit records (AuditRecord, AuditContext)
  - 9 structured event factories for all auditable domains
  - Async, queue-backed writer with batch-flush to MySQL + structlog
  - FastAPI middleware for per-request audit context injection
  - Service-layer decorators for zero-boilerplate function auditing

Quick start:

    # In FastAPI lifespan:
    from app.audit.writer import get_audit_writer
    await get_audit_writer().start()
    yield
    await get_audit_writer().stop(drain_timeout=30.0)

    # In create_application():
    from app.audit.middleware import AuditMiddleware
    app.add_middleware(AuditMiddleware)

    # On a service function:
    from app.audit.decorators import audit_llm_call
    @audit_llm_call(operation="policy_evaluation", tier="medium")
    async def evaluate_policy(...): ...

    # Manual emit:
    from app.audit import emit
    from app.audit.events import decision_event
    emit(decision_event(...))
"""

from app.audit.context import (
    AuditContext,
    build_context_from_request,
    build_system_context,
    get_audit_context,
    reset_audit_context,
    set_audit_context,
    update_case_id,
)
from app.audit.decorators import (
    audit_action,
    audit_extraction,
    audit_llm_call,
    audit_ocr,
    audit_retrieval,
)
from app.audit.events import (
    api_request_event,
    clarification_event,
    decision_event,
    error_event,
    extraction_event,
    llm_call_event,
    ocr_event,
    retrieval_event,
    reviewer_action_event,
)
from app.audit.middleware import AuditMiddleware
from app.audit.models import (
    AuditActorType,
    AuditCategory,
    AuditRecord,
    AuditSeverity,
    hash_sensitive,
    mask_member_id,
)
from app.audit.writer import emit, get_audit_writer

__all__ = [
    # Context
    "AuditContext",
    "build_context_from_request",
    "build_system_context",
    "get_audit_context",
    "reset_audit_context",
    "set_audit_context",
    "update_case_id",
    # Decorators
    "audit_action",
    "audit_extraction",
    "audit_llm_call",
    "audit_ocr",
    "audit_retrieval",
    # Event factories
    "api_request_event",
    "clarification_event",
    "decision_event",
    "error_event",
    "extraction_event",
    "llm_call_event",
    "ocr_event",
    "retrieval_event",
    "reviewer_action_event",
    # Middleware
    "AuditMiddleware",
    # Models
    "AuditActorType",
    "AuditCategory",
    "AuditRecord",
    "AuditSeverity",
    "hash_sensitive",
    "mask_member_id",
    # Writer
    "emit",
    "get_audit_writer",
]
