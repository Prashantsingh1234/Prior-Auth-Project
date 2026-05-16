"""
Security tests for Role-Based Access Control (RBAC).

Verifies:
- Provider role cannot access reviewer-only endpoints
- Reviewer role cannot access admin-only endpoints
- Admin role has full access
- Providers can only see their own cases
- Assign endpoint is admin-only
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.enums import CaseStatus


def _make_provider_token(test_settings, provider_id: str = "provider-uuid-123") -> str:
    from app.core.security.jwt import create_access_token
    with patch("app.core.security.jwt.get_settings", return_value=test_settings):
        return create_access_token(subject=provider_id, role="provider")


def _make_reviewer_token(test_settings, reviewer_id: str = "reviewer-uuid-456") -> str:
    from app.core.security.jwt import create_access_token
    with patch("app.core.security.jwt.get_settings", return_value=test_settings):
        return create_access_token(subject=reviewer_id, role="reviewer")


def _make_admin_token(test_settings, admin_id: str = "admin-uuid-789") -> str:
    from app.core.security.jwt import create_access_token
    with patch("app.core.security.jwt.get_settings", return_value=test_settings):
        return create_access_token(subject=admin_id, role="admin")


class TestReviewerOnlyEndpoints:
    """These endpoints require at minimum the 'reviewer' role."""

    @pytest.mark.asyncio
    async def test_provider_cannot_approve_case(
        self, async_client: AsyncClient, test_settings
    ):
        provider_token = _make_provider_token(test_settings)
        response = await async_client.post(
            "/api/v1/review/some-case-id/approve",
            json={"rationale": "Approve this case."},
            headers={"Authorization": f"Bearer {provider_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_provider_cannot_deny_case(
        self, async_client: AsyncClient, test_settings
    ):
        provider_token = _make_provider_token(test_settings)
        response = await async_client.post(
            "/api/v1/review/some-case-id/deny",
            json={"rationale": "This case should be denied per policy."},
            headers={"Authorization": f"Bearer {provider_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_provider_cannot_escalate_case(
        self, async_client: AsyncClient, test_settings
    ):
        provider_token = _make_provider_token(test_settings)
        response = await async_client.post(
            "/api/v1/review/some-case-id/escalate",
            json={"reason": "Complex case."},
            headers={"Authorization": f"Bearer {provider_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_provider_cannot_access_metrics(
        self, async_client: AsyncClient, test_settings
    ):
        provider_token = _make_provider_token(test_settings)
        response = await async_client.get(
            "/api/v1/metrics",
            headers={"Authorization": f"Bearer {provider_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_reviewer_can_approve_case(
        self, async_client: AsyncClient, test_settings
    ):
        """Reviewer should pass RBAC check (may fail for other reasons like 404)."""
        reviewer_token = _make_reviewer_token(test_settings)

        mock_case = MagicMock()
        mock_case.id = "test-case-id"
        mock_case.case_number = "PA-001"
        mock_case.status = CaseStatus.UNDER_REVIEW
        mock_case.ai_recommendation = "DENY"
        mock_case.provider_id = str(uuid.uuid4())
        mock_case.deleted_at = None

        with (
            patch("app.api.routes.review.PACaseRepository") as MockRepo,
            patch("app.api.routes.review.ReviewerActionRepository"),
            patch("app.api.routes.review.DecisionRepository"),
            patch("app.api.routes.review.TaskPublisher"),
        ):
            repo = AsyncMock()
            repo.get_by_id = AsyncMock(return_value=mock_case)
            repo.transition_status = AsyncMock()
            MockRepo.return_value = repo

            response = await async_client.post(
                "/api/v1/review/test-case-id/approve",
                json={"rationale": "Patient meets all criteria per policy review."},
                headers={"Authorization": f"Bearer {reviewer_token}"},
            )
        # Should not be 403 (RBAC passed) — may be 200 or other error
        assert response.status_code != 403


class TestAdminOnlyEndpoints:
    """Assign endpoint is admin-only."""

    @pytest.mark.asyncio
    async def test_reviewer_cannot_assign_reviewer(
        self, async_client: AsyncClient, test_settings
    ):
        reviewer_token = _make_reviewer_token(test_settings)
        response = await async_client.post(
            "/api/v1/review/some-case-id/assign",
            json={"reviewer_id": "some-reviewer-uuid"},
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_provider_cannot_assign_reviewer(
        self, async_client: AsyncClient, test_settings
    ):
        provider_token = _make_provider_token(test_settings)
        response = await async_client.post(
            "/api/v1/review/some-case-id/assign",
            json={"reviewer_id": "some-reviewer-uuid"},
            headers={"Authorization": f"Bearer {provider_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_assign_reviewer(
        self, async_client: AsyncClient, test_settings
    ):
        admin_token = _make_admin_token(test_settings)

        mock_case = MagicMock()
        mock_case.id = "test-case-id"
        mock_case.case_number = "PA-001"
        mock_case.status = CaseStatus.UNDER_REVIEW
        mock_case.deleted_at = None

        with (
            patch("app.api.routes.review.PACaseRepository") as MockRepo,
            patch("app.api.routes.review.ReviewerActionRepository"),
        ):
            repo = AsyncMock()
            repo.get_by_id = AsyncMock(return_value=mock_case)
            repo.assign_reviewer = AsyncMock()
            MockRepo.return_value = repo

            response = await async_client.post(
                "/api/v1/review/test-case-id/assign",
                json={"reviewer_id": "new-reviewer-uuid"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert response.status_code != 403


class TestProviderAccessControl:
    """Providers can only see their own cases."""

    @pytest.mark.asyncio
    async def test_provider_cannot_see_other_providers_case(
        self, async_client: AsyncClient, test_settings
    ):
        provider_a_token = _make_provider_token(test_settings, provider_id="provider-a")
        other_provider_id = "provider-b"

        mock_case = MagicMock()
        mock_case.id = "case-belonging-to-b"
        mock_case.case_number = "PA-001"
        mock_case.status = CaseStatus.UNDER_REVIEW
        mock_case.provider_id = other_provider_id  # Belongs to provider B
        mock_case.deleted_at = None

        with patch("app.api.routes.cases.PACaseRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_with_all_relations = AsyncMock(return_value=mock_case)
            MockRepo.return_value = repo

            response = await async_client.get(
                "/api/v1/cases/case-belonging-to-b",
                headers={"Authorization": f"Bearer {provider_a_token}"},
            )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_provider_can_see_own_case(
        self, async_client: AsyncClient, test_settings
    ):
        provider_id = "provider-abc"
        provider_token = _make_provider_token(test_settings, provider_id=provider_id)

        mock_case = MagicMock()
        mock_case.id = "my-case-id"
        mock_case.case_number = "PA-002"
        mock_case.status = CaseStatus.SUBMITTED
        mock_case.provider_id = provider_id  # Provider's own case
        mock_case.patient = MagicMock(first_name="Jane", last_name="Smith", member_id="M1")
        mock_case.provider = MagicMock(npi="1234567890")
        mock_case.documents = []
        mock_case.entities = []
        mock_case.policy_matches = []
        mock_case.evaluations = []
        mock_case.clarifications = []
        mock_case.reviewer_actions = []
        mock_case.decision = None
        mock_case.deleted_at = None

        with (
            patch("app.api.routes.cases.PACaseRepository") as MockRepo,
            patch("app.api.routes.cases.ReviewerActionRepository"),
        ):
            repo = AsyncMock()
            repo.get_with_all_relations = AsyncMock(return_value=mock_case)
            MockRepo.return_value = repo

            response = await async_client.get(
                "/api/v1/cases/my-case-id",
                headers={"Authorization": f"Bearer {provider_token}"},
            )
        # RBAC passed — provider owns this case
        assert response.status_code != 403

    @pytest.mark.asyncio
    async def test_reviewer_can_see_any_case(
        self, async_client: AsyncClient, test_settings
    ):
        reviewer_token = _make_reviewer_token(test_settings)

        mock_case = MagicMock()
        mock_case.id = "any-case-id"
        mock_case.case_number = "PA-003"
        mock_case.status = CaseStatus.UNDER_REVIEW
        mock_case.provider_id = "some-provider"
        mock_case.patient = MagicMock(first_name="John", last_name="Doe", member_id="M2")
        mock_case.provider = MagicMock(npi="0987654321")
        mock_case.documents = []
        mock_case.entities = []
        mock_case.policy_matches = []
        mock_case.evaluations = []
        mock_case.clarifications = []
        mock_case.reviewer_actions = []
        mock_case.decision = None
        mock_case.deleted_at = None

        with (
            patch("app.api.routes.cases.PACaseRepository") as MockRepo,
            patch("app.api.routes.cases.ReviewerActionRepository"),
        ):
            repo = AsyncMock()
            repo.get_with_all_relations = AsyncMock(return_value=mock_case)
            MockRepo.return_value = repo

            response = await async_client.get(
                "/api/v1/cases/any-case-id",
                headers={"Authorization": f"Bearer {reviewer_token}"},
            )
        assert response.status_code != 403
