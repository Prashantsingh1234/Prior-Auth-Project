"""
Response schemas for case detail and list endpoints.

Converts ORM models → clean API shapes, handling field name differences:
  PACase.id                → case_id
  PACase.ai_reasoning_summary → ai_rationale
  UploadedDocument.id     → document_id
  ExtractedEntity.id      → entity_id
  Evaluation.id           → criterion_id
  ReviewerAction.id       → event_id
  ReviewerAction.created_at → timestamp
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.api.schemas.common import BaseSchema


# ----------------------------------------------------------
# Patient
# ----------------------------------------------------------

class PatientSchema(BaseSchema):
    patient_id: str
    first_name: str
    last_name: str
    date_of_birth: str       # ISO date string
    member_id: str | None
    gender: str | None
    plan_id: str | None      # insurance_plan_id

    @classmethod
    def from_orm(cls, patient: Any) -> "PatientSchema":
        return cls(
            patient_id=str(patient.id),
            first_name=patient.first_name,
            last_name=patient.last_name,
            date_of_birth=str(patient.date_of_birth) if patient.date_of_birth else "",
            member_id=patient.member_id,
            gender=getattr(patient, "gender", None),
            plan_id=getattr(patient, "insurance_plan_id", None),
        )


# ----------------------------------------------------------
# Provider
# ----------------------------------------------------------

class ProviderSchema(BaseSchema):
    provider_id: str
    npi: str
    specialty: str | None
    organization: str | None
    phone: str | None
    fax: str | None
    # Derived full name
    first_name: str | None
    last_name: str | None

    @classmethod
    def from_orm(cls, provider: Any) -> "ProviderSchema":
        return cls(
            provider_id=str(provider.id),
            npi=provider.npi,
            specialty=getattr(provider, "specialty", None),
            organization=getattr(provider, "organization_name", None),
            phone=getattr(provider, "phone", None),
            fax=getattr(provider, "fax", None),
            first_name=getattr(provider, "first_name", None),
            last_name=getattr(provider, "last_name", None),
        )


# ----------------------------------------------------------
# Document
# ----------------------------------------------------------

class DocumentSchema(BaseSchema):
    document_id: str
    document_type: str
    original_filename: str
    file_size_bytes: int
    content_type: str
    ocr_confidence: float | None
    ocr_status: str | None
    uploaded_at: datetime

    @classmethod
    def from_orm(cls, doc: Any) -> "DocumentSchema":
        return cls(
            document_id=str(doc.id),
            document_type=doc.document_type,
            original_filename=getattr(doc, "original_filename", ""),
            file_size_bytes=getattr(doc, "file_size_bytes", 0),
            content_type=getattr(doc, "content_type", "application/octet-stream"),
            ocr_confidence=doc.ocr_confidence,
            ocr_status=str(doc.ocr_status) if doc.ocr_status else None,
            uploaded_at=doc.created_at,
        )


# ----------------------------------------------------------
# Extracted Entity
# ----------------------------------------------------------

class BoundingBoxSchema(BaseSchema):
    x: float
    y: float
    width: float
    height: float
    page: int


class ExtractedEntitySchema(BaseSchema):
    entity_id: str
    entity_type: str
    value: str
    normalized_value: str | None
    confidence: float
    source_document_id: str | None
    page_number: int | None
    bounding_box: BoundingBoxSchema | None

    @classmethod
    def from_orm(cls, entity: Any) -> "ExtractedEntitySchema":
        # Bounding box may be stored as JSON or separate columns
        bb_data = getattr(entity, "bounding_box", None)
        bounding_box = None
        if isinstance(bb_data, dict):
            try:
                bounding_box = BoundingBoxSchema(**bb_data)
            except Exception:
                pass

        return cls(
            entity_id=str(entity.id),
            entity_type=str(entity.entity_type),
            value=entity.value,
            normalized_value=getattr(entity, "normalized_value", None),
            confidence=getattr(entity, "confidence_score", 0.0),
            source_document_id=(
                str(entity.source_document_id)
                if getattr(entity, "source_document_id", None)
                else None
            ),
            page_number=getattr(entity, "page_number", None),
            bounding_box=bounding_box,
        )


# ----------------------------------------------------------
# Policy Criteria (from Evaluation model)
# ----------------------------------------------------------

class PolicyChunkSchema(BaseSchema):
    chunk_id: str
    text: str
    source: str
    relevance_score: float


class PolicyCriterionSchema(BaseSchema):
    criterion_id: str
    criterion_name: str
    description: str
    status: str
    evidence: str | None
    policy_reference: str | None
    source_chunks: list[PolicyChunkSchema]

    @classmethod
    def from_orm(cls, evaluation: Any) -> "PolicyCriterionSchema":
        # source_chunks may be stored as JSON in matched_criteria or a related model
        raw_chunks = getattr(evaluation, "source_chunks", None) or []
        if isinstance(raw_chunks, list):
            chunks = [
                PolicyChunkSchema(
                    chunk_id=c.get("chunk_id", str(i)),
                    text=c.get("text", ""),
                    source=c.get("source", ""),
                    relevance_score=float(c.get("relevance_score", 0.0)),
                )
                for i, c in enumerate(raw_chunks)
                if isinstance(c, dict)
            ]
        else:
            chunks = []

        return cls(
            criterion_id=str(evaluation.id),
            criterion_name=getattr(evaluation, "criterion_name", ""),
            description=getattr(evaluation, "description", ""),
            status=str(evaluation.status),
            evidence=getattr(evaluation, "evidence_summary", None),
            policy_reference=getattr(evaluation, "policy_reference", None),
            source_chunks=chunks,
        )


# ----------------------------------------------------------
# Case Decision
# ----------------------------------------------------------

class CaseDecisionSchema(BaseSchema):
    decision_id: str
    outcome: str
    source: str
    rationale: str
    override_reason: str | None
    decided_by: str | None
    decided_at: datetime

    @classmethod
    def from_orm(cls, decision: Any) -> "CaseDecisionSchema":
        return cls(
            decision_id=str(decision.id),
            outcome=str(decision.final_decision),
            source=str(decision.decision_source),
            rationale=getattr(decision, "rationale", ""),
            override_reason=getattr(decision, "override_reason", None),
            decided_by=getattr(decision, "decided_by_id", None),
            decided_at=decision.created_at,
        )


# ----------------------------------------------------------
# Clarification
# ----------------------------------------------------------

class ClarificationSchema(BaseSchema):
    clarification_id: str
    question: str
    generated_by: str
    status: str
    sent_at: datetime
    answered_at: datetime | None
    response: str | None
    attempt_number: int

    @classmethod
    def from_orm(cls, cl: Any) -> "ClarificationSchema":
        return cls(
            clarification_id=str(cl.id),
            question=cl.question,
            generated_by=getattr(cl, "generated_by", "llm"),
            status=str(cl.status),
            sent_at=cl.created_at,
            answered_at=getattr(cl, "answered_at", None),
            response=getattr(cl, "response", None),
            attempt_number=cl.attempt_number,
        )


# ----------------------------------------------------------
# Audit Trail (from ReviewerAction model)
# ----------------------------------------------------------

class AuditEventSchema(BaseSchema):
    event_id: str
    event_type: str
    actor_id: str
    actor_name: str
    actor_role: str
    timestamp: datetime
    note: str | None
    metadata: dict[str, Any]

    @classmethod
    def from_orm(cls, action: Any, actor_name: str = "System") -> "AuditEventSchema":
        return cls(
            event_id=str(action.id),
            event_type=str(action.action_type),
            actor_id=str(action.reviewer_id),
            actor_name=actor_name,
            actor_role="reviewer",
            timestamp=action.created_at,
            note=getattr(action, "rationale", None),
            metadata={},
        )


# ----------------------------------------------------------
# Full Case Detail
# ----------------------------------------------------------

class CaseDetailResponse(BaseSchema):
    case_id: str
    case_number: str
    status: str
    priority: str
    service_type: str | None
    cpt_codes: list[str]
    icd_codes: list[str]
    ai_recommendation: str | None
    ai_confidence_score: float | None
    ai_rationale: str | None
    clarification_count: int
    assigned_reviewer_id: str | None
    submitted_at: datetime | None
    updated_at: datetime

    patient: PatientSchema
    provider: ProviderSchema
    documents: list[DocumentSchema]
    extracted_entities: list[ExtractedEntitySchema]
    policy_criteria: list[PolicyCriterionSchema]
    decision: CaseDecisionSchema | None
    clarifications: list[ClarificationSchema]
    audit_trail: list[AuditEventSchema]

    @classmethod
    def from_orm(cls, case: Any) -> "CaseDetailResponse":
        return cls(
            case_id=str(case.id),
            case_number=case.case_number,
            status=str(case.status),
            priority=str(case.priority),
            service_type=str(case.service_type) if case.service_type else None,
            cpt_codes=case.cpt_codes or [],
            icd_codes=case.icd_codes or [],
            ai_recommendation=case.ai_recommendation,
            ai_confidence_score=case.ai_confidence_score,
            ai_rationale=case.ai_reasoning_summary,
            clarification_count=case.clarification_count,
            assigned_reviewer_id=case.assigned_reviewer_id,
            submitted_at=case.submitted_at,
            updated_at=case.updated_at,
            patient=PatientSchema.from_orm(case.patient),
            provider=ProviderSchema.from_orm(case.provider),
            documents=[DocumentSchema.from_orm(d) for d in (case.documents or [])],
            extracted_entities=[
                ExtractedEntitySchema.from_orm(e) for e in (case.entities or [])
            ],
            policy_criteria=[
                PolicyCriterionSchema.from_orm(ev) for ev in (case.evaluations or [])
            ],
            decision=CaseDecisionSchema.from_orm(case.decision) if case.decision else None,
            clarifications=[
                ClarificationSchema.from_orm(cl) for cl in (case.clarifications or [])
            ],
            audit_trail=[
                AuditEventSchema.from_orm(a) for a in (case.reviewer_actions or [])
            ],
        )


# ----------------------------------------------------------
# Case List Item (lightweight, for queue/list views)
# ----------------------------------------------------------

class CaseListItemSchema(BaseSchema):
    case_id: str
    case_number: str
    status: str
    priority: str
    service_type: str | None
    ai_recommendation: str | None
    ai_confidence_score: float | None
    patient_name: str
    provider_name: str
    submitted_at: datetime | None
    updated_at: datetime
    assigned_reviewer_id: str | None
    clarification_count: int

    @classmethod
    def from_orm(cls, case: Any) -> "CaseListItemSchema":
        patient = case.patient
        provider = case.provider

        patient_name = (
            f"{patient.first_name} {patient.last_name}"
            if patient else "Unknown"
        )
        if provider:
            if getattr(provider, "organization_name", None):
                provider_name = provider.organization_name
            else:
                provider_name = f"{getattr(provider, 'first_name', '')} {getattr(provider, 'last_name', '')}".strip()
        else:
            provider_name = "Unknown"

        return cls(
            case_id=str(case.id),
            case_number=case.case_number,
            status=str(case.status),
            priority=str(case.priority),
            service_type=str(case.service_type) if case.service_type else None,
            ai_recommendation=case.ai_recommendation,
            ai_confidence_score=case.ai_confidence_score,
            patient_name=patient_name,
            provider_name=provider_name,
            submitted_at=case.submitted_at,
            updated_at=case.updated_at,
            assigned_reviewer_id=case.assigned_reviewer_id,
            clarification_count=case.clarification_count,
        )


class CaseListResponse(BaseSchema):
    cases: list[CaseListItemSchema]
    meta: dict[str, Any]


# ----------------------------------------------------------
# Case Filter Query Parameters
# ----------------------------------------------------------

class CaseFilterParams(BaseSchema):
    """Query parameters for GET /cases."""

    model_config = BaseSchema.model_config.copy()
    model_config["extra"] = "ignore"

    status: list[str] | None = Field(default=None)
    priority: list[str] | None = Field(default=None)
    service_type: list[str] | None = Field(default=None)
    assigned_to_me: bool = Field(default=False)
    sort_by: str = Field(default="submitted_at")
    sort_dir: str = Field(default="desc")
