"""
factory-boy model factories for test data generation.

Usage:
    from app.tests.factories import PACaseFactory, PatientFactory

    case = PACaseFactory()
    case_with_ai = PACaseFactory(
        ai_recommendation="APPROVE",
        ai_confidence_score=0.92,
    )
    batch = PACaseFactory.create_batch(10, status=CaseStatus.UNDER_REVIEW)
"""

from __future__ import annotations

import random
import string
import uuid
from datetime import UTC, datetime, timedelta

import factory
from factory import LazyFunction

from app.models.enums import (
    CasePriority,
    CaseStatus,
    ClarificationStatus,
    DecisionOutcome,
    DecisionSource,
    DocumentType,
    EntityType,
    ExtractionMethod,
    OCRProvider,
    OCRStatus,
    ProviderType,
    ReviewerActionType,
    ServiceType,
)


def _uuid() -> str:
    return str(uuid.uuid4())


def _case_number() -> str:
    letters = "".join(random.choices(string.ascii_uppercase, k=6))
    return f"PA-20240101-{letters}"


def _npi() -> str:
    return "".join([str(random.randint(0, 9)) for _ in range(10)])


def _cpt_codes() -> list[str]:
    return random.choice([["95249"], ["70553", "70554"], ["99213"], ["27447"]])


def _icd_codes() -> list[str]:
    return random.choice([["E11.9"], ["I10", "E11.9"], ["M17.11"], ["G35"]])


class PatientFactory(factory.Factory):
    class Meta:
        model = dict

    id = LazyFunction(_uuid)
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    date_of_birth = factory.Faker("date_of_birth", minimum_age=18, maximum_age=90)
    gender = factory.Faker("random_element", elements=["male", "female"])
    member_id = factory.LazyFunction(lambda: f"MBR-{random.randint(100000, 999999)}")
    group_number = factory.LazyFunction(lambda: f"GRP-{random.randint(1000, 9999)}")
    insurance_plan_name = factory.Faker("company")
    insurance_plan_id = factory.LazyFunction(lambda: f"PLN-{random.randint(100, 999)}")
    country = "USA"
    created_at = LazyFunction(lambda: datetime.now(UTC))
    updated_at = LazyFunction(lambda: datetime.now(UTC))
    deleted_at = None


class ProviderFactory(factory.Factory):
    class Meta:
        model = dict

    id = LazyFunction(_uuid)
    npi = LazyFunction(_npi)
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    credentials = factory.Faker("random_element", elements=["MD", "DO", "NP", "PA"])
    specialty = factory.Faker(
        "random_element",
        elements=["Internal Medicine", "Cardiology", "Neurology", "Orthopedics", "Radiology"],
    )
    organization_name = factory.Faker("company")
    provider_type = ProviderType.INDIVIDUAL
    phone = factory.Faker("phone_number")
    fax = factory.Faker("phone_number")
    created_at = LazyFunction(lambda: datetime.now(UTC))
    updated_at = LazyFunction(lambda: datetime.now(UTC))
    deleted_at = None


class PACaseFactory(factory.Factory):
    class Meta:
        model = dict

    id = LazyFunction(_uuid)
    case_number = LazyFunction(_case_number)
    patient_id = LazyFunction(_uuid)
    provider_id = LazyFunction(_uuid)
    assigned_reviewer_id = None
    status = CaseStatus.SUBMITTED
    priority = CasePriority.ROUTINE
    service_type = ServiceType.IMAGING
    cpt_codes = LazyFunction(_cpt_codes)
    icd_codes = LazyFunction(_icd_codes)
    requested_service_description = factory.Faker("sentence", nb_words=12)
    clinical_notes = factory.Faker("paragraph", nb_sentences=5)
    ai_recommendation = None
    ai_confidence_score = None
    ai_reasoning_summary = None
    clarification_count = 0
    submitted_at = LazyFunction(lambda: datetime.now(UTC))
    processing_started_at = None
    review_assigned_at = None
    decided_at = None
    external_reference_id = None
    source_channel = "api"
    case_metadata = {}
    created_at = LazyFunction(lambda: datetime.now(UTC))
    updated_at = LazyFunction(lambda: datetime.now(UTC))
    deleted_at = None


class PACaseUnderReviewFactory(PACaseFactory):
    status = CaseStatus.UNDER_REVIEW
    ai_recommendation = "APPROVE"
    ai_confidence_score = 0.88
    ai_reasoning_summary = "Patient meets clinical criteria for the requested procedure."
    processing_started_at = LazyFunction(lambda: datetime.now(UTC) - timedelta(minutes=30))
    review_assigned_at = LazyFunction(lambda: datetime.now(UTC) - timedelta(minutes=5))


class PACaseApprovedFactory(PACaseFactory):
    status = CaseStatus.APPROVED
    ai_recommendation = "APPROVE"
    ai_confidence_score = 0.91
    decided_at = LazyFunction(lambda: datetime.now(UTC))


class PACaseDeniedFactory(PACaseFactory):
    status = CaseStatus.DENIED
    ai_recommendation = "DENY"
    ai_confidence_score = 0.86
    decided_at = LazyFunction(lambda: datetime.now(UTC))


class PACasePendingClarificationFactory(PACaseFactory):
    status = CaseStatus.PENDING_CLARIFICATION
    ai_confidence_score = 0.52
    clarification_count = 1


class DocumentFactory(factory.Factory):
    class Meta:
        model = dict

    id = LazyFunction(_uuid)
    case_id = LazyFunction(_uuid)
    document_type = DocumentType.CLINICAL_NOTES
    original_filename = "clinical_notes.pdf"
    stored_filename = LazyFunction(lambda: f"{uuid.uuid4()}.pdf")
    storage_path = LazyFunction(lambda: f"cases/{uuid.uuid4()}/documents/doc.pdf")
    file_size_bytes = factory.Faker("random_int", min=1024, max=5_000_000)
    content_type = "application/pdf"
    ocr_status = OCRStatus.PENDING
    ocr_provider = OCRProvider.NONE
    ocr_confidence = None
    processing_attempts = 0
    created_at = LazyFunction(lambda: datetime.now(UTC))
    updated_at = LazyFunction(lambda: datetime.now(UTC))
    deleted_at = None


class ClarificationFactory(factory.Factory):
    class Meta:
        model = dict

    id = LazyFunction(_uuid)
    case_id = LazyFunction(_uuid)
    attempt_number = 1
    status = ClarificationStatus.PENDING
    question = "Please provide additional documentation supporting medical necessity."
    questions = factory.LazyAttribute(lambda o: [o.question])
    missing_criteria = ["medical_necessity"]
    response = None
    answered_at = None
    generated_by = "llm"
    response_deadline = LazyFunction(lambda: datetime.now(UTC) + timedelta(hours=48))
    created_at = LazyFunction(lambda: datetime.now(UTC))
    updated_at = LazyFunction(lambda: datetime.now(UTC))


class ClarificationAnsweredFactory(ClarificationFactory):
    status = ClarificationStatus.ANSWERED
    response = "The patient has been diagnosed with Type 2 Diabetes for 3 years."
    answered_at = LazyFunction(lambda: datetime.now(UTC) - timedelta(hours=2))


class DecisionFactory(factory.Factory):
    class Meta:
        model = dict

    id = LazyFunction(_uuid)
    case_id = LazyFunction(_uuid)
    final_decision = DecisionOutcome.APPROVE
    decision_source = DecisionSource.AI_RECOMMENDATION
    rationale = "Patient meets all clinical criteria for continuous glucose monitoring."
    override_reason = None
    denial_reason_code = None
    ai_recommendation = DecisionOutcome.APPROVE
    decided_by_id = LazyFunction(_uuid)
    decided_at = LazyFunction(lambda: datetime.now(UTC))
    created_at = LazyFunction(lambda: datetime.now(UTC))


class DecisionDenialFactory(DecisionFactory):
    final_decision = DecisionOutcome.DENY
    decision_source = DecisionSource.AI_RECOMMENDATION
    ai_recommendation = DecisionOutcome.DENY
    rationale = "Documentation does not meet policy criteria for medical necessity."
    denial_reason_code = "NOT_MEDICALLY_NECESSARY"


class DecisionOverrideFactory(DecisionFactory):
    final_decision = DecisionOutcome.APPROVE
    decision_source = DecisionSource.REVIEWER_OVERRIDE
    ai_recommendation = DecisionOutcome.DENY
    override_reason = "Clinical notes not captured in AI extraction; reviewer confirmed."


class ReviewerActionFactory(factory.Factory):
    class Meta:
        model = dict

    id = LazyFunction(_uuid)
    case_id = LazyFunction(_uuid)
    reviewer_id = LazyFunction(_uuid)
    action_type = ReviewerActionType.VIEWED
    rationale = None
    created_at = LazyFunction(lambda: datetime.now(UTC))


class ExtractedEntityFactory(factory.Factory):
    class Meta:
        model = dict

    id = LazyFunction(_uuid)
    case_id = LazyFunction(_uuid)
    entity_type = EntityType.DIAGNOSIS_CODE
    entity_value = "E11.9"
    normalized_value = "E11.9"
    confidence = 0.95
    extraction_method = ExtractionMethod.LLM
    source_document_id = LazyFunction(_uuid)
    source_page = 1
    source_text = "Patient diagnosed with Type 2 Diabetes mellitus without complications (E11.9)"
    created_at = LazyFunction(lambda: datetime.now(UTC))


# ---------------------------------------------------------------
# Convenience builders for API payload dicts
# ---------------------------------------------------------------

def make_pa_request_payload(**overrides) -> dict:
    """Return a valid POST /pa-requests request body dict."""
    payload = {
        "patient": {
            "first_name": "Jane",
            "last_name": "Smith",
            "date_of_birth": "1975-03-15",
            "gender": "female",
            "member_id": "MBR-123456",
            "group_number": "GRP-4567",
            "insurance_plan_name": "BlueCross PPO",
            "insurance_plan_id": "PLN-100",
        },
        "provider": {
            "npi": "1234567890",
            "first_name": "Robert",
            "last_name": "Chen",
            "specialty": "Internal Medicine",
            "organization_name": "Metro Medical Center",
            "phone": "555-100-2000",
            "fax": "555-100-2001",
        },
        "service_type": "IMAGING",
        "cpt_codes": ["95249"],
        "icd_codes": ["E11.9"],
        "priority": "ROUTINE",
        "requested_service_description": "Continuous glucose monitor insertion.",
        "clinical_notes": "Patient has had Type 2 Diabetes for 3 years, poorly controlled.",
        "source_channel": "api",
    }
    payload.update(overrides)
    return payload


def make_approve_payload(**overrides) -> dict:
    payload = {"rationale": "Patient meets all clinical criteria per current guidelines."}
    payload.update(overrides)
    return payload


def make_deny_payload(**overrides) -> dict:
    payload = {
        "rationale": "Documentation does not meet medical necessity criteria.",
        "denial_reason_code": "NOT_MEDICALLY_NECESSARY",
    }
    payload.update(overrides)
    return payload


def make_pend_payload(**overrides) -> dict:
    payload = {
        "rationale": "Awaiting additional lab results from treating physician.",
        "pending_reason": "Additional documentation required",
    }
    payload.update(overrides)
    return payload


def make_escalate_payload(**overrides) -> dict:
    payload = {"reason": "Complex case requiring senior clinical review."}
    payload.update(overrides)
    return payload
