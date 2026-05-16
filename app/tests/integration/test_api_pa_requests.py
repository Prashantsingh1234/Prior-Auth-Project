"""
Integration tests for POST /pa-requests and GET /cases endpoints.

Tests the full HTTP request/response cycle against the ASGI app
with all infrastructure (DB, Redis, queue) mocked at the repository level.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.enums import CasePriority, CaseStatus, ServiceType
from app.tests.factories import make_pa_request_payload


def _make_mock_patient(patient_id: str | None = None):
    p = MagicMock()
    p.id = patient_id or str(uuid.uuid4())
    p.first_name = "Jane"
    p.last_name = "Smith"
    p.member_id = "MBR-001"
    return p


def _make_mock_provider(provider_id: str | None = None):
    p = MagicMock()
    p.id = provider_id or str(uuid.uuid4())
    p.npi = "1234567890"
    p.first_name = "Bob"
    p.last_name = "Chen"
    return p


def _make_mock_case(case_id: str | None = None, **overrides):
    from datetime import UTC, datetime
    c = MagicMock()
    c.id = case_id or str(uuid.uuid4())
    c.case_number = "PA-20240101-ABCDEF"
    c.status = CaseStatus.SUBMITTED
    c.priority = CasePriority.ROUTINE
    c.service_type = ServiceType.IMAGING
    c.cpt_codes = ["95249"]
    c.icd_codes = ["E11.9"]
    c.submitted_at = datetime.now(UTC)
    c.patient_id = str(uuid.uuid4())
    c.provider_id = str(uuid.uuid4())
    c.clarification_count = 0
    c.deleted_at = None
    for k, v in overrides.items():
        setattr(c, k, v)
    return c


@pytest.fixture
def pa_request_mocks():
    """Patch all repository and queue dependencies for PA request tests."""
    mock_patient = _make_mock_patient()
    mock_provider = _make_mock_provider()
    mock_case = _make_mock_case()

    with (
        patch("app.api.routes.pa_requests.PatientRepository") as MockPatient,
        patch("app.api.routes.pa_requests.ProviderRepository") as MockProvider,
        patch("app.api.routes.pa_requests.PACaseRepository") as MockCase,
        patch("app.api.routes.pa_requests.TaskPublisher") as MockPublisher,
    ):
        patient_repo = AsyncMock()
        patient_repo.find_by_member_id = AsyncMock(return_value=None)
        patient_repo.create = AsyncMock(return_value=mock_patient)
        patient_repo.get_by_id = AsyncMock(return_value=mock_patient)
        MockPatient.return_value = patient_repo

        provider_repo = AsyncMock()
        provider_repo.find_by_npi = AsyncMock(return_value=None)
        provider_repo.create = AsyncMock(return_value=mock_provider)
        MockProvider.return_value = provider_repo

        case_repo = AsyncMock()
        case_repo.get_cases_for_patient = AsyncMock(return_value=[])
        case_repo.create_case = AsyncMock(return_value=mock_case)
        case_repo.count_by_status = AsyncMock(return_value={})
        case_repo.get_reviewer_queue = AsyncMock(return_value=[])
        MockCase.return_value = case_repo

        publisher = AsyncMock()
        publisher.publish = AsyncMock()
        MockPublisher.return_value = publisher

        yield {
            "patient_repo": patient_repo,
            "provider_repo": provider_repo,
            "case_repo": case_repo,
            "mock_patient": mock_patient,
            "mock_provider": mock_provider,
            "mock_case": mock_case,
        }


class TestSubmitPARequest:

    @pytest.mark.asyncio
    async def test_returns_202_on_valid_request(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        pa_request_mocks: dict,
    ):
        response = await async_client.post(
            "/api/v1/pa-requests",
            json=make_pa_request_payload(),
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_response_contains_case_id(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        pa_request_mocks: dict,
    ):
        response = await async_client.post(
            "/api/v1/pa-requests",
            json=make_pa_request_payload(),
            headers=auth_headers_reviewer,
        )
        body = response.json()
        assert "data" in body
        assert "case_id" in body["data"]

    @pytest.mark.asyncio
    async def test_response_contains_case_number(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        pa_request_mocks: dict,
    ):
        response = await async_client.post(
            "/api/v1/pa-requests",
            json=make_pa_request_payload(),
            headers=auth_headers_reviewer,
        )
        body = response.json()
        assert "case_number" in body["data"]

    @pytest.mark.asyncio
    async def test_returns_401_without_auth(self, async_client: AsyncClient):
        response = await async_client.post(
            "/api/v1/pa-requests",
            json=make_pa_request_payload(),
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_422_on_invalid_npi(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
    ):
        payload = make_pa_request_payload()
        payload["provider"]["npi"] = "12345"  # invalid — only 5 digits
        response = await async_client.post(
            "/api/v1/pa-requests",
            json=payload,
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_returns_422_on_empty_cpt_codes(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
    ):
        payload = make_pa_request_payload(cpt_codes=[])
        response = await async_client.post(
            "/api/v1/pa-requests",
            json=payload,
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_returns_422_on_missing_service_type(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
    ):
        payload = make_pa_request_payload()
        del payload["service_type"]
        response = await async_client.post(
            "/api/v1/pa-requests",
            json=payload,
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_returns_409_on_duplicate_cpt_for_active_case(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        pa_request_mocks: dict,
    ):
        # Existing active case with same CPT code
        existing_case = _make_mock_case(status=CaseStatus.UNDER_REVIEW, cpt_codes=["95249"])
        pa_request_mocks["case_repo"].get_cases_for_patient = AsyncMock(return_value=[existing_case])

        response = await async_client.post(
            "/api/v1/pa-requests",
            json=make_pa_request_payload(cpt_codes=["95249"]),
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_reuses_existing_patient_by_member_id(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        pa_request_mocks: dict,
    ):
        """If patient already exists by member_id, don't create a duplicate."""
        existing_patient = _make_mock_patient()
        pa_request_mocks["patient_repo"].find_by_member_id = AsyncMock(return_value=existing_patient)

        response = await async_client.post(
            "/api/v1/pa-requests",
            json=make_pa_request_payload(),
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 202
        # Should NOT have called create on patient repo
        pa_request_mocks["patient_repo"].create.assert_not_called()

    @pytest.mark.asyncio
    async def test_reuses_existing_provider_by_npi(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        pa_request_mocks: dict,
    ):
        existing_provider = _make_mock_provider()
        pa_request_mocks["provider_repo"].find_by_npi = AsyncMock(return_value=existing_provider)

        response = await async_client.post(
            "/api/v1/pa-requests",
            json=make_pa_request_payload(),
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 202
        pa_request_mocks["provider_repo"].create.assert_not_called()

    @pytest.mark.asyncio
    async def test_success_response_is_wrapped_in_envelope(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        pa_request_mocks: dict,
    ):
        response = await async_client.post(
            "/api/v1/pa-requests",
            json=make_pa_request_payload(),
            headers=auth_headers_reviewer,
        )
        body = response.json()
        assert body["success"] is True
        assert "data" in body


class TestListCases:

    @pytest.fixture
    def list_mocks(self, pa_request_mocks):
        """Extend pa_request_mocks with list-specific data."""
        cases = [_make_mock_case() for _ in range(3)]
        pa_request_mocks["case_repo"].get_reviewer_queue = AsyncMock(return_value=cases)
        pa_request_mocks["case_repo"].count_by_status = AsyncMock(
            return_value={CaseStatus.SUBMITTED: 3}
        )
        return pa_request_mocks

    @pytest.mark.asyncio
    async def test_returns_200_for_reviewer(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        list_mocks: dict,
    ):
        response = await async_client.get("/api/v1/cases", headers=auth_headers_reviewer)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_401_without_auth(self, async_client: AsyncClient):
        with patch("app.api.routes.pa_requests.PACaseRepository"):
            response = await async_client.get("/api/v1/cases")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_response_contains_cases_key(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        list_mocks: dict,
    ):
        response = await async_client.get("/api/v1/cases", headers=auth_headers_reviewer)
        body = response.json()
        assert "data" in body
