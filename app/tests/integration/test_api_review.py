"""
Integration tests for the reviewer workflow endpoints.

POST /review/{case_id}/approve
POST /review/{case_id}/deny
POST /review/{case_id}/pend
POST /review/{case_id}/escalate
POST /review/{case_id}/notes
POST /review/{case_id}/assign
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.enums import CasePriority, CaseStatus, DecisionOutcome
from app.tests.factories import (
    make_approve_payload,
    make_deny_payload,
    make_escalate_payload,
    make_pend_payload,
)


def _make_case(status=CaseStatus.UNDER_REVIEW, **overrides):
    from datetime import UTC, datetime

    case = MagicMock()
    case.id = str(uuid.uuid4())
    case.case_number = "PA-20240101-ABCDEF"
    case.status = status
    case.priority = CasePriority.ROUTINE
    case.ai_recommendation = "APPROVE"
    case.ai_confidence_score = 0.88
    case.ai_reasoning_summary = "Meets clinical criteria."
    case.provider_id = str(uuid.uuid4())
    case.assigned_reviewer_id = None
    case.decided_at = None
    case.is_decided = status in {CaseStatus.APPROVED, CaseStatus.DENIED, CaseStatus.CANCELLED}
    case.deleted_at = None
    case.created_at = datetime.now(UTC)
    case.updated_at = datetime.now(UTC)
    for k, v in overrides.items():
        setattr(case, k, v)
    return case


@pytest.fixture
def review_mocks():
    """Patch all dependencies used by the review router."""
    case_id = str(uuid.uuid4())
    mock_case = _make_case()
    mock_case.id = case_id
    updated_case = _make_case(status=CaseStatus.APPROVED)
    updated_case.id = case_id

    with (
        patch("app.api.routes.review.PACaseRepository") as MockCaseRepo,
        patch("app.api.routes.review.ReviewerActionRepository") as MockActionRepo,
        patch("app.api.routes.review.DecisionRepository") as MockDecisionRepo,
        patch("app.api.routes.review.TaskPublisher") as MockPublisher,
    ):
        case_repo = AsyncMock()
        case_repo.get_by_id = AsyncMock(side_effect=lambda cid: mock_case if cid == case_id else None)
        case_repo.transition_status = AsyncMock()
        case_repo.assign_reviewer = AsyncMock()
        case_repo.get_by_id = AsyncMock(return_value=mock_case)
        MockCaseRepo.return_value = case_repo

        action_repo = AsyncMock()
        action_repo.create = AsyncMock()
        MockActionRepo.return_value = action_repo

        decision_repo = AsyncMock()
        decision_repo.create = AsyncMock()
        MockDecisionRepo.return_value = decision_repo

        publisher = AsyncMock()
        publisher.publish = AsyncMock()
        MockPublisher.return_value = publisher

        # After transition, return updated case
        def get_by_id_side_effect(cid):
            return updated_case

        case_repo.get_by_id = AsyncMock(side_effect=get_by_id_side_effect)

        yield {
            "case_id": case_id,
            "mock_case": mock_case,
            "updated_case": updated_case,
            "case_repo": case_repo,
            "action_repo": action_repo,
        }


class TestApproveCase:

    @pytest.mark.asyncio
    async def test_approve_returns_200(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        review_mocks: dict,
    ):
        case_id = review_mocks["case_id"]
        response = await async_client.post(
            f"/api/v1/review/{case_id}/approve",
            json=make_approve_payload(),
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_approve_response_contains_case_id(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        review_mocks: dict,
    ):
        case_id = review_mocks["case_id"]
        response = await async_client.post(
            f"/api/v1/review/{case_id}/approve",
            json=make_approve_payload(),
            headers=auth_headers_reviewer,
        )
        body = response.json()
        assert "data" in body
        assert "case_id" in body["data"]

    @pytest.mark.asyncio
    async def test_approve_requires_reviewer_role(
        self,
        async_client: AsyncClient,
        review_mocks: dict,
    ):
        """Provider token should be rejected with 403."""
        from app.core.config.settings import get_settings
        from app.core.security.jwt import create_access_token
        from unittest.mock import patch as p

        with p("app.core.security.jwt.get_settings", return_value=get_settings()):
            provider_token = create_access_token(subject="provider-uuid", role="provider")

        case_id = review_mocks["case_id"]
        response = await async_client.post(
            f"/api/v1/review/{case_id}/approve",
            json=make_approve_payload(),
            headers={"Authorization": f"Bearer {provider_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_approve_returns_401_without_auth(
        self,
        async_client: AsyncClient,
        review_mocks: dict,
    ):
        case_id = review_mocks["case_id"]
        response = await async_client.post(
            f"/api/v1/review/{case_id}/approve",
            json=make_approve_payload(),
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_approve_already_decided_case_returns_409(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        review_mocks: dict,
    ):
        decided_case = _make_case(status=CaseStatus.APPROVED)
        review_mocks["case_repo"].get_by_id = AsyncMock(return_value=decided_case)

        case_id = review_mocks["case_id"]
        response = await async_client.post(
            f"/api/v1/review/{case_id}/approve",
            json=make_approve_payload(),
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_approve_nonexistent_case_returns_404(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        review_mocks: dict,
    ):
        review_mocks["case_repo"].get_by_id = AsyncMock(return_value=None)
        response = await async_client.post(
            "/api/v1/review/nonexistent-id/approve",
            json=make_approve_payload(),
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 404


class TestDenyCase:

    @pytest.mark.asyncio
    async def test_deny_returns_200(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        review_mocks: dict,
    ):
        denied_case = _make_case(status=CaseStatus.DENIED)
        review_mocks["case_repo"].get_by_id = AsyncMock(
            side_effect=[_make_case(), denied_case]
        )

        case_id = review_mocks["case_id"]
        response = await async_client.post(
            f"/api/v1/review/{case_id}/deny",
            json=make_deny_payload(),
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_deny_requires_rationale_min_length(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        review_mocks: dict,
    ):
        case_id = review_mocks["case_id"]
        response = await async_client.post(
            f"/api/v1/review/{case_id}/deny",
            json={"rationale": "Too short"},  # < 10 chars
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 422


class TestPendCase:

    @pytest.mark.asyncio
    async def test_pend_returns_200(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        review_mocks: dict,
    ):
        pended_case = _make_case(status=CaseStatus.PENDED)
        review_mocks["case_repo"].get_by_id = AsyncMock(
            side_effect=[_make_case(), pended_case]
        )

        case_id = review_mocks["case_id"]
        response = await async_client.post(
            f"/api/v1/review/{case_id}/pend",
            json=make_pend_payload(),
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_pend_missing_rationale_returns_422(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        review_mocks: dict,
    ):
        case_id = review_mocks["case_id"]
        response = await async_client.post(
            f"/api/v1/review/{case_id}/pend",
            json={"pending_reason": "Missing labs"},  # no rationale
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 422


class TestEscalateCase:

    @pytest.mark.asyncio
    async def test_escalate_returns_200(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        review_mocks: dict,
    ):
        escalated_case = _make_case(status=CaseStatus.ESCALATED)
        review_mocks["case_repo"].get_by_id = AsyncMock(
            side_effect=[_make_case(), escalated_case]
        )

        case_id = review_mocks["case_id"]
        response = await async_client.post(
            f"/api/v1/review/{case_id}/escalate",
            json=make_escalate_payload(),
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_escalate_with_target_reviewer(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        review_mocks: dict,
    ):
        escalated_case = _make_case(status=CaseStatus.ESCALATED)
        review_mocks["case_repo"].get_by_id = AsyncMock(
            side_effect=[_make_case(), escalated_case]
        )

        case_id = review_mocks["case_id"]
        response = await async_client.post(
            f"/api/v1/review/{case_id}/escalate",
            json={"reason": "Complex case.", "escalate_to": "senior-reviewer-uuid"},
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 200
        review_mocks["case_repo"].assign_reviewer.assert_called_once_with(
            case_id, "senior-reviewer-uuid"
        )


class TestAddNote:

    @pytest.mark.asyncio
    async def test_add_note_returns_201(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        review_mocks: dict,
    ):
        review_mocks["case_repo"].get_by_id = AsyncMock(return_value=_make_case())

        case_id = review_mocks["case_id"]
        response = await async_client.post(
            f"/api/v1/review/{case_id}/notes",
            json={"note": "Reviewed additional clinical documentation. Case looks strong."},
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 201


class TestAssignReviewer:

    @pytest.mark.asyncio
    async def test_assign_requires_admin_role(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        review_mocks: dict,
    ):
        """Reviewer (non-admin) should get 403."""
        case_id = review_mocks["case_id"]
        response = await async_client.post(
            f"/api/v1/review/{case_id}/assign",
            json={"reviewer_id": "some-reviewer-uuid"},
            headers=auth_headers_reviewer,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_assign_succeeds_for_admin(
        self,
        async_client: AsyncClient,
        auth_headers_admin: dict,
        review_mocks: dict,
    ):
        review_mocks["case_repo"].get_by_id = AsyncMock(side_effect=[_make_case(), _make_case()])

        case_id = review_mocks["case_id"]
        response = await async_client.post(
            f"/api/v1/review/{case_id}/assign",
            json={"reviewer_id": "new-reviewer-uuid"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
