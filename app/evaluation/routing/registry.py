"""
Model capability and cost registry.

The registry is the source of truth for:
  - which model IDs are available
  - their tier classification (FAST / MEDIUM / STRONG)
  - their context window and feature capabilities
  - their per-token pricing (for cost efficiency scoring)
  - their default routing priority per domain

Prices are in USD per 1,000 tokens.  Update when provider pricing changes.
The registry is read-only at runtime — mutate only in this file or via
inject_model() in tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.evaluation.models import EvalDomain, ModelTier


@dataclass(frozen=True)
class ModelInfo:
    """Static description of a model and its capabilities."""
    model_id:              str
    tier:                  ModelTier
    provider:              str              # "openai" | "anthropic" | "local"
    context_window_tokens: int
    supports_json_mode:    bool = True
    supports_vision:       bool = False
    supports_function_calling: bool = True

    # Pricing (USD per 1k tokens)
    cost_per_1k_prompt:      float = 0.0
    cost_per_1k_completion:  float = 0.0

    # Routing priority per domain (higher = prefer this model for that domain)
    # 0 = not used for this domain
    domain_priority: dict[str, int] = field(default_factory=dict)

    # Human-readable notes
    notes: str = ""

    @property
    def cost_per_1k_total(self) -> float:
        return self.cost_per_1k_prompt + self.cost_per_1k_completion

    def priority_for(self, domain: EvalDomain) -> int:
        return self.domain_priority.get(domain.value, 0)


# ---------------------------------------------------------------------------
# Built-in model definitions
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, ModelInfo] = {
    # ---- OpenAI ----
    "gpt-4o": ModelInfo(
        model_id="gpt-4o",
        tier=ModelTier.STRONG,
        provider="openai",
        context_window_tokens=128_000,
        supports_vision=True,
        cost_per_1k_prompt=0.005,
        cost_per_1k_completion=0.015,
        domain_priority={
            "reasoning": 10,
            "end_to_end": 10,
            "extraction": 8,
        },
        notes="Best accuracy; use for complex reasoning and final decisions",
    ),
    "gpt-4o-mini": ModelInfo(
        model_id="gpt-4o-mini",
        tier=ModelTier.MEDIUM,
        provider="openai",
        context_window_tokens=128_000,
        cost_per_1k_prompt=0.000150,
        cost_per_1k_completion=0.000600,
        domain_priority={
            "extraction": 10,
            "retrieval": 10,
            "clarification": 8,
            "reasoning": 5,
        },
        notes="Cost-efficient; default for extraction and retrieval",
    ),
    "gpt-3.5-turbo": ModelInfo(
        model_id="gpt-3.5-turbo",
        tier=ModelTier.FAST,
        provider="openai",
        context_window_tokens=16_385,
        cost_per_1k_prompt=0.000500,
        cost_per_1k_completion=0.001500,
        domain_priority={
            "extraction": 5,
            "retrieval": 5,
        },
        notes="Fast and cheap; use for simple extraction tasks only",
    ),
    # ---- Anthropic ----
    "claude-opus-4-7": ModelInfo(
        model_id="claude-opus-4-7",
        tier=ModelTier.STRONG,
        provider="anthropic",
        context_window_tokens=200_000,
        cost_per_1k_prompt=0.015,
        cost_per_1k_completion=0.075,
        domain_priority={
            "reasoning": 10,
            "end_to_end": 9,
        },
        notes="Strongest reasoning; use for critical/escalation cases",
    ),
    "claude-sonnet-4-6": ModelInfo(
        model_id="claude-sonnet-4-6",
        tier=ModelTier.MEDIUM,
        provider="anthropic",
        context_window_tokens=200_000,
        cost_per_1k_prompt=0.003,
        cost_per_1k_completion=0.015,
        domain_priority={
            "reasoning": 8,
            "extraction": 9,
            "clarification": 9,
            "end_to_end": 8,
        },
        notes="Best overall balance; default for most PA reasoning",
    ),
    "claude-haiku-4-5": ModelInfo(
        model_id="claude-haiku-4-5",
        tier=ModelTier.FAST,
        provider="anthropic",
        context_window_tokens=200_000,
        cost_per_1k_prompt=0.000800,
        cost_per_1k_completion=0.004000,
        domain_priority={
            "extraction": 8,
            "retrieval": 8,
            "clarification": 7,
        },
        notes="Very fast; use for bulk extraction and simple classification",
    ),
}


# ---------------------------------------------------------------------------
# Registry interface
# ---------------------------------------------------------------------------

class ModelRegistry:
    """
    Read-only access to model capability and cost data.

    The singleton instance is created at the bottom of this module.
    Use `get_model_registry()` to access it.
    """

    def __init__(self, models: dict[str, ModelInfo]) -> None:
        self._models = dict(models)

    def get(self, model_id: str) -> ModelInfo | None:
        return self._models.get(model_id)

    def require(self, model_id: str) -> ModelInfo:
        info = self._models.get(model_id)
        if info is None:
            raise KeyError(f"Model '{model_id}' not in registry")
        return info

    def all_models(self) -> list[ModelInfo]:
        return list(self._models.values())

    def models_for_tier(self, tier: ModelTier) -> list[ModelInfo]:
        return [m for m in self._models.values() if m.tier == tier]

    def models_for_domain(self, domain: EvalDomain) -> list[ModelInfo]:
        """Return models with non-zero priority for the given domain, sorted by priority."""
        candidates = [
            m for m in self._models.values()
            if m.priority_for(domain) > 0
        ]
        return sorted(candidates, key=lambda m: m.priority_for(domain), reverse=True)

    def default_model(self, domain: EvalDomain) -> ModelInfo | None:
        """Return the highest-priority model for a domain."""
        candidates = self.models_for_domain(domain)
        return candidates[0] if candidates else None

    def inject(self, model: ModelInfo) -> None:
        """Add or replace a model entry — intended for tests only."""
        self._models[model.model_id] = model

    def cost_estimate(
        self,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        info = self.get(model_id)
        if info is None:
            return 0.0
        return (
            prompt_tokens / 1_000 * info.cost_per_1k_prompt
            + completion_tokens / 1_000 * info.cost_per_1k_completion
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_registry_instance: ModelRegistry | None = None


def get_model_registry() -> ModelRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ModelRegistry(_REGISTRY)
    return _registry_instance
