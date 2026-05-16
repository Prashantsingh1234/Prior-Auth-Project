"""
Integration tests for clarification endpoints.

POST /clarification/{case_id}/respond
GET  /clarification/{case_id}
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.enums import CasePriority, CaseStatus, ClarificationStatus


def _make_case(status=CaseStatus.PENDING_CLARIFICATION, **overrides):
    from datetime import UTC, datetime

    c = MagicMock()
    c.id = str(uuid.uuid4())
    c.case_number = "PA-20240101-ABCDEF"
    c.status = status
    c.priority = CasePriority.ROUTINE
    c.provider_id = str(uuid.uuid4())
    c.clarification_count = 1
    c.deleted_at = None
    c.created_at = datetime.now(UTC)
    c.updated_at = datetime.now(UTC)
    for k, v in overrides.items():
        setattr(c, k, v)
    return c


def _make_clarification(status=ClarificationStatus.PENDING, **overrides):
    from datetime import UTC, datetime

    cl = MagicMock()
    cl.id = str(uuid.uuid4())
    cl.case_id = str(uuid.uuid4())
    cl.status = status
    cl.question = "Please provide additional supporting documentation."
    cl.questions = [cl.question]
    cl.attempt_number = 1
    cl.created_at = datetime.now(UTC)
    cl.answered_at = None
    cl.response = None
    for k, v in overrides.items():
        setattr(cl, k, v)
    return cl


@pytest.fixture
def clarification_mocks():
    case_id = str(uuid.uuid4())
    cl_id = str(uuid.uuid4())
    mock_case = _make_case()
    mock_case.id = case_id
    mock_cl = _make_clarification()
    mock_cl.id = cl_id
    mock_cl.case_id = case_id

    with (
        patch("app.api.routes.clarification.PACaseRepository") as MockCaseRepo,
        patch("app.api.routes.clarification.ClarificationRepository") as MockClRepo,
        patch("app.api.routes.clarification.TaskPublisher") as MockPublisher,
        patch("app.api.routes.clarification.ReviewerActionRepository") as MockActionRepo,
    ):
        case_repo = AsyncMock()
        case_repo.get_by_id = AsyncMock(return_value=mock_case)
        case_repo.increment_clarification_count = AsyncMock()
        case_repo.transition_status = AsyncMock()
        MockCaseRepo.return_value = case_repo

        cl_repo = AsyncMock()
        cl_repo.get_by_id = AsyncMock(return_value=mock_cl)
        cl_repo.get_by_case_id = AsyncMock(return_value=[mock_cl])
        MockClRepo.return_value = cl_repo

        publisher = AsyncMock()
        publisher.publish = AsyncMock()
        MockPublisher.return_value = publisher

        action_repo = AsyncMock()
        action_repo.create = AsyncMock()
        MockActionRepo.return_value = action_repo

        # Updated case after transition
        updated_case = _make_case(status=CaseStatus.PROCESSING)
        updated_case.id = case_id
        updated_case.clarification_count = 2
        case_repo.get_by_id = AsyncMock(side_effect=[mock_case, mock_case, updated_case])

        yield {
            "case_id": case_id,
            "cl_id": cl_id,
            "mock_case": mock_case,
            "mock_cl": mock_cl,
            "case_repo": case_repo,
            "cl_repo": cl_repo,
        }


class TestRespondToClarification:

    @pytest.mark.asyncio
    async def test_respond_returns_200(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        clarification_mocks: dict,
    ):
        case_id = clarification_mocks["case_id"]
        cl_id = clarification_mocks["cl_id"]

        response = await async_client.post(
            f"/api/v1/clarification/{case_id}/respond",
            json={
                "clarification_id": cl_id,
                "response": "The patient has been on insulin therapy for 3 years with HbA1c of 9.2%.",
            },
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_respond_returns_case_id(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        clarification_mocks: dict,
    ):
        case_id = clarification_mocks["case_id"]
        cl_id = clarification_mocks["cl_id"]

        response = await async_client.post(
            f"/api/v1/clarification/{case_id}/respond",
            json={
                "clarification_id": cl_id,
                "response": "Patient has documented diabetes for over 3 years with poor control.",
            },
            headers=auth_headers_reviewer,
        )
        body = response.json()
        assert "case_id" in body["data"]

    @pytest.mark.asyncio
    async def test_respond_returns_401_without_auth(
        self,
        async_client: AsyncClient,
        clarification_mocks: dict,
    ):
        case_id = clarification_mocks["case_id"]
        cl_id = clarification_mocks["cl_id"]

        response = await async_client.post(
            f"/api/v1/clarification/{case_id}/respond",
            json={"clarification_id": cl_id, "response": "Some response here"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_respond_returns_409_when_case_not_pending_clarification(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        clarification_mocks: dict,
    ):
        wrong_status_case = _make_case(status=CaseStatus.UNDER_REVIEW)
        clarification_mocks["case_repo"].get_by_id = AsyncMock(return_value=wrong_status_case)

        case_id = clarification_mocks["case_id"]
        cl_id = clarification_mocks["cl_id"]
        response = await async_client.post(
            f"/api/v1/clarification/{case_id}/respond",
            json={"clarification_id": cl_id, "response": "Patient details provided."},
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_respond_returns_409_when_clarification_already_answered(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        clarification_mocks: dict,
    ):
        answered_cl = _make_clarification(status=ClarificationStatus.ANSWERED)
        answered_cl.case_id = clarification_mocks["case_id"]
        clarification_mocks["cl_repo"].get_by_id = AsyncMock(return_value=answered_cl)

        case_id = clarification_mocks["case_id"]
        response = await async_client.post(
            f"/api/v1/clarification/{case_id}/respond",
            json={
                "clarification_id": answered_cl.id,
                "response": "Already answered this one.",
            },
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_respond_returns_404_when_case_not_found(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        clarification_mocks: dict,
    ):
        clarification_mocks["case_repo"].get_by_id = AsyncMock(return_value=None)
        response = await async_client.post(
            "/api/v1/clarification/nonexistent-id/respond",
            json={"clarification_id": "some-cl-id", "response": "Some response text here."},
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_respond_short_response_returns_422(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        clarification_mocks: dict,
    ):
        case_id = clarification_mocks["case_id"]
        cl_id = clarification_mocks["cl_id"]
        response = await async_client.post(
            f"/api/v1/clarification/{case_id}/respond",
            json={"clarification_id": cl_id, "response": "No"},  # < 5 chars
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_auto_escalates_after_max_clarifications(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        clarification_mocks: dict,
    ):
        """At clarification_count = 2 (already attempted twice), responding triggers auto-escalation."""
        case_id = clarification_mocks["case_id"]
        cl_id = clarification_mocks["cl_id"]

        # Case already at count=2, responding hits the max (3)
        near_max_case = _make_case(status=CaseStatus.PENDING_CLARIFICATION, clarification_count=2)
        near_max_case.id = case_id
        escalated_case = _make_case(status=CaseStatus.ESCALATED, clarification_count=3)
        escalated_case.id = case_id

        clarification_mocks["case_repo"].get_by_id = AsyncMock(
            side_effect=[near_max_case, near_max_case, escalated_case]
        )

        response = await async_client.post(
            f"/api/v1/clarification/{case_id}/respond",
            json={
                "clarification_id": cl_id,
                "response": "Third attempt response with all available documentation provided.",
            },
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 200
        # The case should now be ESCALATED
        body = response.json()
        assert body["data"]["status"] in ("ESCALATED", "CaseStatus.ESCALATED")


class TestListClarifications:

    @pytest.mark.asyncio
    async def test_list_returns_200(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        clarification_mocks: dict,
    ):
        case_id = clarification_mocks["case_id"]
        response = await async_client.get(
            f"/api/v1/clarification/{case_id}",
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_returns_clarification_items(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        clarification_mocks: dict,
    ):
        case_id = clarification_mocks["case_id"]
        response = await async_client.get(
            f"/api/v1/clarification/{case_id}",
            headers=auth_headers_reviewer,
        )
        body = response.json()
        assert "data" in body
        assert isinstance(body["data"], list)

    @pytest.mark.asyncio
    async def test_list_returns_401_without_auth(
        self,
        async_client: AsyncClient,
        clarification_mocks: dict,
    ):
        case_id = clarification_mocks["case_id"]
        response = await async_client.get(f"/api/v1/clarification/{case_id}")
        assert response.status_code == 401
