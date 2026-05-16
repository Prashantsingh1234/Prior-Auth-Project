"""
Integration tests for metrics endpoints.

GET /metrics              — Business KPIs (requires reviewer or admin role)
GET /metrics/prometheus   — Raw Prometheus text (requires reviewer or admin role)
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.enums import CasePriority, CaseStatus


@pytest.fixture
def metrics_mocks():
    """Patch the PA case repository used by the metrics endpoint."""
    status_counts = {
        CaseStatus.SUBMITTED: 10,
        CaseStatus.PROCESSING: 5,
        CaseStatus.UNDER_REVIEW: 20,
        CaseStatus.PENDING_CLARIFICATION: 3,
        CaseStatus.APPROVED: 45,
        CaseStatus.DENIED: 12,
        CaseStatus.PENDED: 8,
        CaseStatus.ESCALATED: 2,
    }
    priority_counts = {
        CasePriority.ROUTINE: 80,
        CasePriority.URGENT: 20,
        CasePriority.EMERGENT: 5,
    }

    with patch("app.api.routes.metrics.PACaseRepository") as MockCaseRepo:
        case_repo = AsyncMock()
        case_repo.count_by_status = AsyncMock(return_value=status_counts)
        case_repo.count_by_priority = AsyncMock(return_value=priority_counts)
        case_repo.session = AsyncMock()

        # Mock the inline SQL calls inside the helper functions
        ai_perf_result = MagicMock()
        ai_perf_result.avg_conf = 0.84
        ai_perf_result.high = 30
        ai_perf_result.medium = 10
        ai_perf_result.low = 5

        clarification_result = MagicMock()
        clarification_result.scalar.return_value = 8

        turnaround_result = MagicMock()
        turnaround_result.scalar.return_value = 12.5

        async def mock_execute(stmt):
            result = MagicMock()
            result.first.return_value = ai_perf_result
            result.scalar.return_value = 8
            return result

        case_repo.session.execute = AsyncMock(side_effect=mock_execute)
        MockCaseRepo.return_value = case_repo

        yield {"case_repo": case_repo, "status_counts": status_counts}


class TestGetBusinessMetrics:

    @pytest.mark.asyncio
    async def test_returns_200_for_reviewer(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        metrics_mocks: dict,
    ):
        response = await async_client.get("/api/v1/metrics", headers=auth_headers_reviewer)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_200_for_admin(
        self,
        async_client: AsyncClient,
        auth_headers_admin: dict,
        metrics_mocks: dict,
    ):
        response = await async_client.get("/api/v1/metrics", headers=auth_headers_admin)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_401_without_auth(
        self,
        async_client: AsyncClient,
        metrics_mocks: dict,
    ):
        response = await async_client.get("/api/v1/metrics")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_403_for_provider_role(
        self,
        async_client: AsyncClient,
        metrics_mocks: dict,
    ):
        from unittest.mock import patch as p
        from app.core.config.settings import get_settings
        from app.core.security.jwt import create_access_token

        with p("app.core.security.jwt.get_settings", return_value=get_settings()):
            provider_token = create_access_token(subject="provider-uuid", role="provider")

        response = await async_client.get(
            "/api/v1/metrics",
            headers={"Authorization": f"Bearer {provider_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_response_has_queue_metrics(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        metrics_mocks: dict,
    ):
        response = await async_client.get("/api/v1/metrics", headers=auth_headers_reviewer)
        body = response.json()
        assert "data" in body
        data = body["data"]
        assert "queue" in data

    @pytest.mark.asyncio
    async def test_response_has_decision_rates(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        metrics_mocks: dict,
    ):
        response = await async_client.get("/api/v1/metrics", headers=auth_headers_reviewer)
        data = response.json()["data"]
        assert "decisions" in data
        decisions = data["decisions"]
        assert "approved" in decisions
        assert "denied" in decisions
        assert "approval_rate" in decisions

    @pytest.mark.asyncio
    async def test_response_has_queue_metrics_fields(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        metrics_mocks: dict,
    ):
        response = await async_client.get("/api/v1/metrics", headers=auth_headers_reviewer)
        data = response.json()["data"]
        queue = data["queue"]
        assert "total_active" in queue
        assert "under_review" in queue
        assert "escalated" in queue

    @pytest.mark.asyncio
    async def test_decision_rates_sum_to_one(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        metrics_mocks: dict,
    ):
        response = await async_client.get("/api/v1/metrics", headers=auth_headers_reviewer)
        decisions = response.json()["data"]["decisions"]
        rate_sum = (
            decisions["approval_rate"]
            + decisions["denial_rate"]
            + decisions["pend_rate"]
        )
        assert abs(rate_sum - 1.0) < 0.01, f"Rates sum to {rate_sum}, expected ~1.0"

    @pytest.mark.asyncio
    async def test_response_has_priority_breakdown(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        metrics_mocks: dict,
    ):
        response = await async_client.get("/api/v1/metrics", headers=auth_headers_reviewer)
        data = response.json()["data"]
        assert "priority_breakdown" in data
        pb = data["priority_breakdown"]
        assert "routine" in pb
        assert "urgent" in pb
        assert "emergent" in pb

    @pytest.mark.asyncio
    async def test_response_has_generated_at_timestamp(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        metrics_mocks: dict,
    ):
        response = await async_client.get("/api/v1/metrics", headers=auth_headers_reviewer)
        data = response.json()["data"]
        assert "generated_at" in data

    @pytest.mark.asyncio
    async def test_success_envelope_is_correct(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        metrics_mocks: dict,
    ):
        response = await async_client.get("/api/v1/metrics", headers=auth_headers_reviewer)
        body = response.json()
        assert body["success"] is True


class TestPrometheusMetrics:

    @pytest.mark.asyncio
    async def test_prometheus_requires_auth(
        self,
        async_client: AsyncClient,
        metrics_mocks: dict,
    ):
        response = await async_client.get("/api/v1/metrics/prometheus")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_prometheus_returns_text_content_type(
        self,
        async_client: AsyncClient,
        auth_headers_reviewer: dict,
        metrics_mocks: dict,
    ):
        response = await async_client.get(
            "/api/v1/metrics/prometheus",
            headers=auth_headers_reviewer,
        )
        # Either returns prometheus text or 503 if prometheus_client unavailable
        assert response.status_code in (200, 503)
        if response.status_code == 200:
            assert "text/plain" in response.headers.get("content-type", "")
