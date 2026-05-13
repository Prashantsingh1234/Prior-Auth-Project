"""
Unit tests for ORM model construction and properties.

Tests model instantiation, default values, properties,
and enum validation without hitting the database.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.models.clarification import Clarification
from app.models.decision import Decision
from app.models.document import UploadedDocument
from app.models.enums import (
    CasePriority,
    CaseStatus,
    ClarificationStatus,
    DecisionOutcome,
    DecisionSource,
    OCRProvider,
    OCRStatus,
    ProviderType,
)
from app.models.pa_case import PACase
from app.models.patient import Patient
from app.models.provider import Provider


class TestPatientModel:

    def test_patient_construction(self) -> None:
        p = Patient(
            id=str(uuid.uuid4()),
            first_name="John",
            last_name="Doe",
            member_id="MBR-001",
        )
        assert p.first_name == "John"
        assert p.last_name == "Doe"
        assert p.member_id == "MBR-001"

    def test_patient_default_country(self) -> None:
        p = Patient(id=str(uuid.uuid4()), first_name="Jane", last_name="Smith", member_id="M2")
        assert p.country == "USA"

    def test_patient_repr(self) -> None:
        p = Patient(id="abc", first_name="J", last_name="Smith", member_id="M1")
        assert "Smith" in repr(p)
        assert "M1" in repr(p)


class TestProviderModel:

    def test_provider_individual_display_name(self) -> None:
        p = Provider(
            id=str(uuid.uuid4()),
            npi="1234567890",
            first_name="Alice",
            last_name="Chen",
            credentials="MD",
            provider_type=ProviderType.INDIVIDUAL,
        )
        assert p.display_name == "Alice Chen, MD"

    def test_provider_organization_display_name(self) -> None:
        p = Provider(
            id=str(uuid.uuid4()),
            npi="9876543210",
            organization_name="Metro Hospital",
            provider_type=ProviderType.ORGANIZATION,
        )
        assert p.display_name == "Metro Hospital"

    def test_provider_fallback_display_name_is_npi(self) -> None:
        p = Provider(
            id=str(uuid.uuid4()),
            npi="1111111111",
            provider_type=ProviderType.INDIVIDUAL,
        )
        assert p.display_name == "1111111111"


class TestPACaseModel:

    def _make_case(self, **kwargs) -> PACase:
        defaults = dict(
            id=str(uuid.uuid4()),
            case_number="PA-20240101-ABC123",
            patient_id=str(uuid.uuid4()),
            provider_id=str(uuid.uuid4()),
            status=CaseStatus.SUBMITTED,
            priority=CasePriority.ROUTINE,
            cpt_codes=["95249"],
            icd_codes=["E11.9"],
            clarification_count=0,
        )
        defaults.update(kwargs)
        return PACase(**defaults)

    def test_case_default_status(self) -> None:
        case = self._make_case()
        assert case.status == CaseStatus.SUBMITTED

    def test_case_is_decided_false_for_submitted(self) -> None:
        case = self._make_case(status=CaseStatus.SUBMITTED)
        assert case.is_decided is False

    def test_case_is_decided_true_for_approved(self) -> None:
        case = self._make_case(status=CaseStatus.APPROVED)
        assert case.is_decided is True

    def test_case_can_be_clarified(self) -> None:
        case = self._make_case(
            status=CaseStatus.PENDING_CLARIFICATION,
            clarification_count=1,
        )
        assert case.can_be_clarified is True

    def test_case_cannot_be_clarified_at_max(self) -> None:
        case = self._make_case(
            status=CaseStatus.PENDING_CLARIFICATION,
            clarification_count=3,  # max reached
        )
        assert case.can_be_clarified is False

    def test_case_repr(self) -> None:
        case = self._make_case()
        assert "PA-20240101-ABC123" in repr(case)


class TestDocumentModel:

    def _make_doc(self, **kwargs) -> UploadedDocument:
        defaults = dict(
            id=str(uuid.uuid4()),
            case_id=str(uuid.uuid4()),
            original_filename="test.pdf",
            stored_filename="test_stored.pdf",
            storage_path="/uploads/test_stored.pdf",
            ocr_provider=OCRProvider.NONE,
            ocr_status=OCRStatus.PENDING,
            processing_attempts=0,
        )
        defaults.update(kwargs)
        return UploadedDocument(**defaults)

    def test_is_ocr_complete_false_when_pending(self) -> None:
        doc = self._make_doc(ocr_status=OCRStatus.PENDING)
        assert doc.is_ocr_complete is False

    def test_is_ocr_complete_true_when_completed(self) -> None:
        doc = self._make_doc(ocr_status=OCRStatus.COMPLETED)
        assert doc.is_ocr_complete is True

    def test_needs_fallback_on_failed(self) -> None:
        doc = self._make_doc(
            ocr_status=OCRStatus.FAILED,
            ocr_provider=OCRProvider.AZURE,
        )
        assert doc.needs_fallback is True

    def test_needs_fallback_on_low_confidence(self) -> None:
        doc = self._make_doc(
            ocr_status=OCRStatus.COMPLETED,
            ocr_provider=OCRProvider.AZURE,
            ocr_confidence=0.55,  # Below 0.80 threshold
        )
        assert doc.needs_fallback is True

    def test_no_fallback_when_high_confidence(self) -> None:
        doc = self._make_doc(
            ocr_status=OCRStatus.COMPLETED,
            ocr_provider=OCRProvider.AZURE,
            ocr_confidence=0.95,
        )
        assert doc.needs_fallback is False


class TestDecisionModel:

    def _make_decision(self, **kwargs) -> Decision:
        defaults = dict(
            id=str(uuid.uuid4()),
            case_id=str(uuid.uuid4()),
            final_decision=DecisionOutcome.APPROVE,
            decision_source=DecisionSource.AI_RECOMMENDATION,
            ai_recommendation=DecisionOutcome.APPROVE,
        )
        defaults.update(kwargs)
        return Decision(**defaults)

    def test_is_override_false_for_ai_recommendation(self) -> None:
        d = self._make_decision(decision_source=DecisionSource.AI_RECOMMENDATION)
        assert d.is_override is False

    def test_is_override_true_for_reviewer_override(self) -> None:
        d = self._make_decision(decision_source=DecisionSource.REVIEWER_OVERRIDE)
        assert d.is_override is True

    def test_ai_agreed_true_when_matching(self) -> None:
        d = self._make_decision(
            final_decision=DecisionOutcome.APPROVE,
            ai_recommendation=DecisionOutcome.APPROVE,
        )
        assert d.ai_agreed is True

    def test_ai_agreed_false_when_different(self) -> None:
        d = self._make_decision(
            final_decision=DecisionOutcome.APPROVE,
            ai_recommendation=DecisionOutcome.DENY,
        )
        assert d.ai_agreed is False

    def test_ai_agreed_none_when_no_recommendation(self) -> None:
        d = self._make_decision(ai_recommendation=None)
        assert d.ai_agreed is None


class TestClarificationModel:

    def test_is_overdue_false_when_no_deadline(self) -> None:
        c = Clarification(
            id=str(uuid.uuid4()),
            case_id=str(uuid.uuid4()),
            attempt_number=1,
            status=ClarificationStatus.PENDING,
            missing_criteria=[],
            questions=[],
        )
        assert c.is_overdue is False

    def test_is_overdue_false_when_already_answered(self) -> None:
        from datetime import UTC, datetime, timedelta
        c = Clarification(
            id=str(uuid.uuid4()),
            case_id=str(uuid.uuid4()),
            attempt_number=1,
            status=ClarificationStatus.ANSWERED,
            missing_criteria=[],
            questions=[],
            response_deadline=datetime.now(UTC) - timedelta(hours=1),
        )
        assert c.is_overdue is False

    def test_is_overdue_true_when_deadline_passed(self) -> None:
        from datetime import UTC, datetime, timedelta
        c = Clarification(
            id=str(uuid.uuid4()),
            case_id=str(uuid.uuid4()),
            attempt_number=1,
            status=ClarificationStatus.PENDING,
            missing_criteria=[],
            questions=[],
            response_deadline=datetime.now(UTC) - timedelta(hours=1),
        )
        assert c.is_overdue is True

    def test_is_overdue_false_when_deadline_future(self) -> None:
        from datetime import UTC, datetime, timedelta
        c = Clarification(
            id=str(uuid.uuid4()),
            case_id=str(uuid.uuid4()),
            attempt_number=1,
            status=ClarificationStatus.PENDING,
            missing_criteria=[],
            questions=[],
            response_deadline=datetime.now(UTC) + timedelta(hours=24),
        )
        assert c.is_overdue is False
