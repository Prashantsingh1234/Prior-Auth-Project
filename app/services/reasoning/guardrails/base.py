"""
Base guardrail interface and shared context object.

All guardrails implement BaseGuardrail and are called via check().
Results are aggregated in the PostLLMValidator composite checker.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.services.reasoning.models import GuardrailResult, GuardrailViolation


@dataclass
class GuardrailContext:
    """
    Context passed to every guardrail check.

    Contains both the LLM output (for post checks) and the input state (for
    pre checks and groundedness verification).
    """
    case_id:           str
    raw_output:        str | None = None           # raw LLM response string
    parsed_output:     dict[str, Any] | None = None  # JSON-parsed response
    clinical_summary:  str = ""
    policy_chunks:     list[str] = field(default_factory=list)  # source texts for grounding
    policy_metadata:   list[dict] = field(default_factory=list)
    query_cpt_codes:   list[str] = field(default_factory=list)
    query_icd_codes:   list[str] = field(default_factory=list)
    extracted_entities: dict[str, Any] = field(default_factory=dict)
    model_tier:        str = "medium"
    attempt_number:    int = 1
    prior_violations:  list[GuardrailViolation] = field(default_factory=list)


class BaseGuardrail(ABC):
    """Abstract base for all guardrail implementations."""

    name: str = "base_guardrail"

    @abstractmethod
    async def check(self, ctx: GuardrailContext) -> GuardrailResult:
        """Run the guardrail check and return a result."""

    async def _timed_check(self, ctx: GuardrailContext) -> GuardrailResult:
        """Wrap check() with latency tracking."""
        t0 = time.perf_counter()
        result = await self.check(ctx)
        result.latency_ms = (time.perf_counter() - t0) * 1000
        result.guardrail_name = self.name
        return result

    def _pass(self) -> GuardrailResult:
        return GuardrailResult(passed=True, guardrail_name=self.name)

    def _fail(self, violations: list[GuardrailViolation]) -> GuardrailResult:
        return GuardrailResult(passed=False, violations=violations, guardrail_name=self.name)
