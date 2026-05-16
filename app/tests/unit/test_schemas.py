"""
Unit tests for Pydantic request/response schemas.

Verifies field validation, model validators, normalization,
and error messages for all API schemas.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestPatientSubmitSchema:
    """PatientSubmitSchema requires patient_id OR (first_name + last_name + member_id)."""

    def _import(self):
        from app.api.schemas.pa_request import PatientSubmitSchema
        return PatientSubmitSchema

    def test_valid_with_patient_id(self):
        schema = self._import()
        obj = schema(patient_id="uuid-1234")
        assert obj.patient_id == "uuid-1234"

    def test_valid_with_name_and_member_id(self):
        schema = self._import()
        obj = schema(
            first_name="Jane",
            last_name="Smith",
            member_id="MBR-001",
        )
        assert obj.first_name == "Jane"

    def test_invalid_when_no_patient_id_and_no_name(self):
        schema = self._import()
        with pytest.raises(ValidationError) as exc_info:
            schema(member_id="MBR-001")  # missing first_name/last_name
        errors = exc_info.value.errors()
        assert any("first_name" in str(e) or "last_name" in str(e) or "patient_id" in str(e)
                   for e in errors)

    def test_date_of_birth_accepted_as_string(self):
        schema = self._import()
        obj = schema(
            first_name="Jane",
            last_name="Smith",
            member_id="MBR-001",
            date_of_birth="1980-06-15",
        )
        assert obj.date_of_birth is not None


class TestProviderSubmitSchema:
    """NPI must be exactly 10 digits."""

    def _import(self):
        from app.api.schemas.pa_request import ProviderSubmitSchema
        return ProviderSubmitSchema

    def test_valid_10_digit_npi(self):
        schema = self._import()
        obj = schema(npi="1234567890", first_name="Bob", last_name="Chen")
        assert obj.npi == "1234567890"

    def test_rejects_9_digit_npi(self):
        schema = self._import()
        with pytest.raises(ValidationError):
            schema(npi="123456789", first_name="Bob", last_name="Chen")

    def test_rejects_11_digit_npi(self):
        schema = self._import()
        with pytest.raises(ValidationError):
            schema(npi="12345678901", first_name="Bob", last_name="Chen")

    def test_rejects_npi_with_letters(self):
        schema = self._import()
        with pytest.raises(ValidationError):
            schema(npi="12345ABCDE", first_name="Bob", last_name="Chen")

    def test_rejects_empty_npi(self):
        schema = self._import()
        with pytest.raises(ValidationError):
            schema(npi="", first_name="Bob", last_name="Chen")


class TestPARequestCreate:
    """CPT/ICD codes are normalized to uppercase; required fields enforced."""

    def _import(self):
        from app.api.schemas.pa_request import PARequestCreate
        return PARequestCreate

    def _valid_payload(self, **overrides):
        payload = {
            "patient": {
                "first_name": "Jane",
                "last_name": "Smith",
                "member_id": "MBR-001",
            },
            "provider": {
                "npi": "1234567890",
                "first_name": "Bob",
                "last_name": "Chen",
            },
            "service_type": "IMAGING",
            "cpt_codes": ["95249"],
            "icd_codes": ["e11.9"],
            "priority": "ROUTINE",
            "requested_service_description": "CGM insertion",
        }
        payload.update(overrides)
        return payload

    def test_valid_request_constructs(self):
        schema = self._import()
        obj = schema(**self._valid_payload())
        assert obj.service_type.value == "IMAGING"

    def test_icd_codes_normalized_to_uppercase(self):
        schema = self._import()
        obj = schema(**self._valid_payload(icd_codes=["e11.9", "i10"]))
        assert "E11.9" in obj.icd_codes
        assert "I10" in obj.icd_codes

    def test_cpt_codes_normalized_to_uppercase(self):
        schema = self._import()
        obj = schema(**self._valid_payload(cpt_codes=["95249"]))
        assert "95249" in obj.cpt_codes

    def test_missing_service_type_raises(self):
        schema = self._import()
        payload = self._valid_payload()
        del payload["service_type"]
        with pytest.raises(ValidationError):
            schema(**payload)

    def test_empty_cpt_codes_raises(self):
        schema = self._import()
        with pytest.raises(ValidationError):
            schema(**self._valid_payload(cpt_codes=[]))

    def test_invalid_service_type_raises(self):
        schema = self._import()
        with pytest.raises(ValidationError):
            schema(**self._valid_payload(service_type="INVALID_TYPE"))

    def test_invalid_priority_raises(self):
        schema = self._import()
        with pytest.raises(ValidationError):
            schema(**self._valid_payload(priority="SUPER_URGENT"))


class TestApproveRequest:

    def _import(self):
        from app.api.schemas.review import ApproveRequest
        return ApproveRequest

    def test_valid_with_rationale(self):
        schema = self._import()
        obj = schema(rationale="Meets all clinical criteria per current guidelines.")
        assert obj.rationale is not None

    def test_valid_without_rationale(self):
        schema = self._import()
        obj = schema()
        assert obj.rationale is None

    def test_override_reason_optional(self):
        schema = self._import()
        obj = schema(override_reason="AI missed key clinical note")
        assert obj.override_reason == "AI missed key clinical note"


class TestDenyRequest:

    def _import(self):
        from app.api.schemas.review import DenyRequest
        return DenyRequest

    def test_valid_deny_request(self):
        schema = self._import()
        obj = schema(rationale="Does not meet medical necessity criteria for this diagnosis.")
        assert obj.rationale is not None

    def test_rationale_too_short_raises(self):
        schema = self._import()
        with pytest.raises(ValidationError):
            schema(rationale="Short")  # less than 10 chars

    def test_denial_reason_code_optional(self):
        schema = self._import()
        obj = schema(rationale="Does not meet medical necessity criteria for this diagnosis.")
        assert obj.denial_reason_code is None

    def test_denial_reason_code_accepted(self):
        schema = self._import()
        obj = schema(
            rationale="Does not meet medical necessity criteria for this diagnosis.",
            denial_reason_code="NOT_MEDICALLY_NECESSARY",
        )
        assert obj.denial_reason_code == "NOT_MEDICALLY_NECESSARY"


class TestPendRequest:

    def _import(self):
        from app.api.schemas.review import PendRequest
        return PendRequest

    def test_valid_pend_request(self):
        schema = self._import()
        obj = schema(
            rationale="Awaiting additional lab documentation from treating physician.",
            pending_reason="Lab results pending",
        )
        assert obj.rationale is not None
        assert obj.pending_reason is not None

    def test_missing_rationale_raises(self):
        schema = self._import()
        with pytest.raises(ValidationError):
            schema(pending_reason="Waiting for labs")


class TestEscalateRequest:

    def _import(self):
        from app.api.schemas.review import EscalateRequest
        return EscalateRequest

    def test_valid_escalate_without_target(self):
        schema = self._import()
        obj = schema(reason="Complex clinical scenario requiring senior review.")
        assert obj.escalate_to is None

    def test_valid_escalate_with_target(self):
        schema = self._import()
        obj = schema(reason="Complex clinical scenario.", escalate_to="senior-reviewer-uuid")
        assert obj.escalate_to == "senior-reviewer-uuid"


class TestClarificationRespondRequest:

    def _import(self):
        from app.api.schemas.clarification import ClarificationRespondRequest
        return ClarificationRespondRequest

    def test_valid_response(self):
        schema = self._import()
        obj = schema(
            clarification_id="cl-uuid-1234",
            response="Patient has had diabetes for 3 years, HbA1c is 9.2%.",
        )
        assert obj.clarification_id == "cl-uuid-1234"

    def test_response_too_short_raises(self):
        schema = self._import()
        with pytest.raises(ValidationError):
            schema(clarification_id="cl-uuid-1234", response="No")  # < 5 chars

    def test_missing_clarification_id_raises(self):
        schema = self._import()
        with pytest.raises(ValidationError):
            schema(response="Patient has been diagnosed with diabetes mellitus type 2.")


class TestCommonSchemas:

    def test_success_response_wraps_data(self):
        from app.api.schemas.common import SuccessResponse
        resp = SuccessResponse(data={"key": "value"})
        assert resp.data == {"key": "value"}
        assert resp.success is True

    def test_success_response_model_dump(self):
        from app.api.schemas.common import SuccessResponse
        resp = SuccessResponse(data={"case_id": "abc"})
        d = resp.model_dump(mode="json")
        assert d["success"] is True
        assert d["data"]["case_id"] == "abc"

    def test_pagination_meta_build(self):
        from app.api.schemas.common import PaginationMeta

        class FakePagination:
            page = 2
            page_size = 20

        meta = PaginationMeta.build(page=2, page_size=20, total=55)
        assert meta.page == 2
        assert meta.page_size == 20
        assert meta.total == 55
        assert meta.total_pages == 3  # ceil(55/20)
        assert meta.has_next is True
        assert meta.has_prev is True
