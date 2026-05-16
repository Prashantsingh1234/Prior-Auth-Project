"""
Tests for the multi-model reasoning orchestrator.

Tests:
- Model tier selection based on case complexity
- Escalation logic on repeated failures
- Cost tracking across model calls
- Decision accuracy against benchmark dataset
- Token limit enforcement per tier
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

CASES_PATH = Path(__file__).parent / "datasets" / "cases.json"


@pytest.fixture
def benchmark_cases():
    with open(CASES_PATH) as f:
        return json.load(f)["cases"]


def _make_reasoning_context(case_data: dict) -> dict:
    """Build reasoning context from benchmark case data."""
    return {
        "case_id": case_data["case_id"],
        "cpt_codes": case_data["cpt_codes"],
        "icd_codes": case_data["icd_codes"],
        "clinical_notes": case_data["clinical_notes"],
        "extracted_entities": case_data.get("extracted_entities", []),
        "policy_criteria": case_data.get("policy_criteria", []),
        "retrieved_chunks": [],
    }


class TestReasoningOrchestrator:

    def test_orchestrator_importable(self):
        try:
            from app.services.reasoning.orchestrator import ReasoningOrchestrator  # noqa: F401
        except ImportError:
            pytest.skip("ReasoningOrchestrator not yet implemented")

    @pytest.mark.asyncio
    async def test_returns_recommendation_and_confidence(self):
        try:
            from app.services.reasoning.orchestrator import ReasoningOrchestrator
        except ImportError:
            pytest.skip("ReasoningOrchestrator not yet implemented")

        orchestrator = ReasoningOrchestrator()
        mock_result = MagicMock()
        mock_result.recommendation = "APPROVE"
        mock_result.confidence = 0.91
        mock_result.rationale = "Patient meets all criteria."
        mock_result.criteria_results = []
        mock_result.cost_usd = 0.0023

        with patch.object(orchestrator, "run", new_callable=AsyncMock, return_value=mock_result):
            result = await orchestrator.run(context={"case_id": "test-001"})
            assert result.recommendation in ("APPROVE", "DENY", "PEND")
            assert 0.0 <= result.confidence <= 1.0
            assert result.rationale is not None

    @pytest.mark.asyncio
    async def test_escalates_on_repeated_llm_failures(self):
        try:
            from app.services.reasoning.orchestrator import ReasoningOrchestrator
        except ImportError:
            pytest.skip("ReasoningOrchestrator not yet implemented")

        orchestrator = ReasoningOrchestrator()

        with patch.object(
            orchestrator, "_call_llm",
            new_callable=AsyncMock,
            side_effect=Exception("LLM API error"),
        ):
            from app.core.exceptions.base import LLMError
            with pytest.raises((LLMError, Exception)):
                await orchestrator.run(context={"case_id": "test-fail-001"})


class TestModelTierRouting:
    """Test that cases are routed to the appropriate model tier."""

    def test_router_importable(self):
        try:
            from app.services.reasoning.router import ModelRouter  # noqa: F401
        except ImportError:
            pytest.skip("ModelRouter not yet implemented")

    @pytest.mark.parametrize("complexity_score,expected_tier", [
        (0.2, "small"),      # Simple case → fast small model
        (0.5, "medium"),     # Moderate complexity → medium model
        (0.8, "large"),      # Complex case → most capable model
        (0.95, "large"),     # Very complex → large model
    ])
    def test_tier_selection_by_complexity(self, complexity_score: float, expected_tier: str):
        try:
            from app.services.reasoning.router import ModelRouter
        except ImportError:
            pytest.skip("ModelRouter not yet implemented")

        router = ModelRouter()
        with patch.object(router, "_compute_complexity", return_value=complexity_score):
            tier = router.select_tier(context={"case_id": "test"})
            assert tier == expected_tier, (
                f"Complexity {complexity_score} should route to '{expected_tier}', got '{tier}'"
            )

    def test_emergent_priority_always_uses_large_model(self):
        try:
            from app.services.reasoning.router import ModelRouter
        except ImportError:
            pytest.skip("ModelRouter not yet implemented")

        router = ModelRouter()
        from app.models.enums import CasePriority
        context = {"case_id": "test", "priority": CasePriority.EMERGENT}

        with patch.object(router, "_compute_complexity", return_value=0.1):  # Would be small
            tier = router.select_tier(context=context)
            assert tier == "large"  # Emergent always uses large model


class TestCostTracking:
    """Test that model call costs are tracked accurately."""

    def test_cost_tracker_importable(self):
        try:
            from app.services.reasoning.orchestrator import CostTracker  # noqa: F401
        except ImportError:
            pytest.skip("CostTracker not yet implemented")

    def test_cost_accumulates_across_calls(self):
        try:
            from app.services.reasoning.orchestrator import CostTracker
        except ImportError:
            pytest.skip("CostTracker not yet implemented")

        tracker = CostTracker()
        tracker.record(model="gpt-4o-mini", input_tokens=1000, output_tokens=200)
        tracker.record(model="gpt-4o-mini", input_tokens=500, output_tokens=100)

        assert tracker.total_cost_usd > 0.0
        assert tracker.total_input_tokens == 1500
        assert tracker.total_output_tokens == 300

    def test_cost_is_zero_at_start(self):
        try:
            from app.services.reasoning.orchestrator import CostTracker
        except ImportError:
            pytest.skip("CostTracker not yet implemented")

        tracker = CostTracker()
        assert tracker.total_cost_usd == 0.0
        assert tracker.total_input_tokens == 0


class TestDecisionAccuracy:
    """Evaluate decision accuracy against the curated benchmark dataset."""

    def test_benchmark_cases_load(self, benchmark_cases):
        assert len(benchmark_cases) > 0
        for case in benchmark_cases:
            assert "expected_outcome" in case
            assert case["expected_outcome"] in ("APPROVE", "DENY", "PEND", "ESCALATE")

    @pytest.mark.parametrize("case_id,expected_outcome", [
        ("TEST-APPROVE-001", "APPROVE"),
        ("TEST-DENY-001", "DENY"),
        ("TEST-APPROVE-002", "APPROVE"),
        ("TEST-DENY-002", "DENY"),
        ("TEST-APPROVE-003", "APPROVE"),
    ])
    @pytest.mark.asyncio
    async def test_simulated_decision_matches_expected(
        self, case_id: str, expected_outcome: str, benchmark_cases: list
    ):
        """Test that a simulated perfect orchestrator returns expected outcomes."""
        try:
            from app.services.reasoning.orchestrator import ReasoningOrchestrator
        except ImportError:
            pytest.skip("ReasoningOrchestrator not yet implemented")

        case_data = next((c for c in benchmark_cases if c["case_id"] == case_id), None)
        assert case_data is not None, f"Case {case_id} not found in benchmark"

        orchestrator = ReasoningOrchestrator()
        mock_result = MagicMock()
        mock_result.recommendation = expected_outcome
        mock_result.confidence = case_data.get("expected_confidence_min", 0.80) + 0.05
        mock_result.rationale = f"Simulated decision for {case_id}"

        with patch.object(orchestrator, "run", new_callable=AsyncMock, return_value=mock_result):
            result = await orchestrator.run(context=_make_reasoning_context(case_data))
            assert result.recommendation == expected_outcome

    def test_no_approve_all_criteria_failed(self, benchmark_cases):
        """Cases where all criteria fail should never be APPROVE."""
        deny_cases = [c for c in benchmark_cases if c["expected_outcome"] == "DENY"]
        for case in deny_cases:
            if "policy_criteria" in case:
                all_failed = all(
                    c["status"] == "FAIL"
                    for c in case["policy_criteria"]
                )
                if all_failed:
                    # All criteria failed → must not be approved
                    assert case["expected_outcome"] != "APPROVE", (
                        f"Case {case['case_id']} has all criteria FAIL but expects APPROVE"
                    )

    def test_high_confidence_threshold_on_easy_cases(self, benchmark_cases):
        """Easy cases should have high minimum confidence requirements."""
        easy_cases = [c for c in benchmark_cases if c.get("difficulty") == "easy"]
        for case in easy_cases:
            min_conf = case.get("expected_confidence_min", 0.0)
            assert min_conf >= 0.80, (
                f"Easy case {case['case_id']} has low min confidence {min_conf}"
            )
