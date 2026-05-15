"""
Routing policies — rules that govern automatic model up/downgrade.

A RoutingPolicy is a named set of thresholds.  When evaluation metrics
for a model fall below (or rise above) those thresholds, the router
automatically switches to a cheaper or stronger model.

Policy hierarchy:
  1. DEFAULT        — production baseline
  2. CONSERVATIVE   — lower thresholds, prefer STRONG tier
  3. COST_OPTIMIZED — higher tolerance for lower accuracy, prefer FAST tier
  4. STRICT         — HIPAA-grade; almost any failure triggers upgrade to STRONG

Policies are immutable dataclasses.  Create custom policies by calling
RoutingPolicy.custom() or instantiating directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.evaluation.models import CaseComplexity, EvalDomain, ModelTier


@dataclass(frozen=True)
class DowngradeRule:
    """
    When this condition is met, route to a cheaper tier.

    metric_name: name of the EvalMetric (e.g. "hallucination", "decision.accuracy")
    threshold:   if metric value *exceeds* this (for rates) or *falls below* this
                 (for quality scores), trigger the rule.  direction controls this.
    direction:   "below" → downgrade if value < threshold (quality metric fell)
                 "above" → downgrade if value > threshold (error rate too high)
    target_tier: which tier to step down to (must be lower than current)
    """
    metric_name: str
    threshold:   float
    direction:   str          # "below" | "above"
    target_tier: ModelTier
    note:        str = ""

    def triggered(self, metric_value: float) -> bool:
        if self.direction == "below":
            return metric_value < self.threshold
        return metric_value > self.threshold


@dataclass(frozen=True)
class UpgradeRule:
    """
    When this condition is met, route to a stronger tier.

    direction:   "below" → upgrade if value < threshold (quality dropped)
                 "above" → upgrade if value > threshold (complexity signal)
    target_tier: which tier to step up to
    """
    metric_name:  str
    threshold:    float
    direction:    str          # "below" | "above"
    target_tier:  ModelTier
    applies_to:   set[CaseComplexity] = field(default_factory=set)  # empty = all
    note:         str = ""

    def triggered(self, metric_value: float, complexity: CaseComplexity) -> bool:
        if self.applies_to and complexity not in self.applies_to:
            return False
        if self.direction == "below":
            return metric_value < self.threshold
        return metric_value > self.threshold


@dataclass(frozen=True)
class RoutingPolicy:
    """
    A named set of downgrade + upgrade rules.

    The router evaluates all rules in order.  The first triggered rule wins.
    Upgrade rules take precedence over downgrade rules when both fire.
    """
    name:           str
    description:    str = ""
    downgrade_rules: tuple[DowngradeRule, ...] = field(default_factory=tuple)
    upgrade_rules:   tuple[UpgradeRule, ...] = field(default_factory=tuple)

    # Complexity → minimum tier mapping (overrides metric-based rules)
    min_tier_by_complexity: dict[str, str] = field(default_factory=dict)

    def min_tier(self, complexity: CaseComplexity) -> ModelTier | None:
        tier_str = self.min_tier_by_complexity.get(complexity.value)
        if tier_str is None:
            return None
        return ModelTier(tier_str)

    def evaluate_upgrades(
        self,
        metrics: dict[str, float],
        complexity: CaseComplexity,
    ) -> UpgradeRule | None:
        """Return the first triggered upgrade rule, or None."""
        for rule in self.upgrade_rules:
            val = metrics.get(rule.metric_name)
            if val is not None and rule.triggered(val, complexity):
                return rule
        return None

    def evaluate_downgrades(
        self,
        metrics: dict[str, float],
    ) -> DowngradeRule | None:
        """Return the first triggered downgrade rule, or None."""
        for rule in self.downgrade_rules:
            val = metrics.get(rule.metric_name)
            if val is not None and rule.triggered(val):
                return rule
        return None


# ---------------------------------------------------------------------------
# Built-in policies
# ---------------------------------------------------------------------------

DEFAULT_POLICY = RoutingPolicy(
    name="default",
    description="Production baseline — balanced accuracy and cost",
    upgrade_rules=(
        UpgradeRule(
            metric_name="hallucination",
            threshold=0.65,
            direction="below",
            target_tier=ModelTier.STRONG,
            note="Hallucination too high — upgrade to STRONG",
        ),
        UpgradeRule(
            metric_name="decision.accuracy",
            threshold=0.80,
            direction="below",
            target_tier=ModelTier.STRONG,
            applies_to={CaseComplexity.HIGH, CaseComplexity.CRITICAL},
            note="Decision accuracy below 80% on complex cases — upgrade",
        ),
        UpgradeRule(
            metric_name="faithfulness",
            threshold=0.70,
            direction="below",
            target_tier=ModelTier.STRONG,
            note="Faithfulness too low — upgrade",
        ),
        UpgradeRule(
            metric_name="reviewer_agreement.exact",
            threshold=0.75,
            direction="below",
            target_tier=ModelTier.STRONG,
            applies_to={CaseComplexity.HIGH, CaseComplexity.CRITICAL},
            note="Low reviewer agreement on complex cases",
        ),
    ),
    downgrade_rules=(
        DowngradeRule(
            metric_name="hallucination",
            threshold=0.90,
            direction="above",       # inverted: above 0.9 means very low hallucination
            target_tier=ModelTier.MEDIUM,
            note="Hallucination very low — can step down to MEDIUM",
        ),
        DowngradeRule(
            metric_name="decision.accuracy",
            threshold=0.90,
            direction="above",
            target_tier=ModelTier.MEDIUM,
            note="High accuracy sustained — consider MEDIUM tier",
        ),
    ),
    min_tier_by_complexity={
        "critical": ModelTier.STRONG.value,
        "high":     ModelTier.MEDIUM.value,
    },
)

CONSERVATIVE_POLICY = RoutingPolicy(
    name="conservative",
    description="Prefer STRONG tier; only downgrade on consistently high accuracy",
    upgrade_rules=(
        UpgradeRule(
            metric_name="hallucination",
            threshold=0.75,
            direction="below",
            target_tier=ModelTier.STRONG,
        ),
        UpgradeRule(
            metric_name="decision.accuracy",
            threshold=0.85,
            direction="below",
            target_tier=ModelTier.STRONG,
        ),
        UpgradeRule(
            metric_name="groundedness",
            threshold=0.70,
            direction="below",
            target_tier=ModelTier.STRONG,
        ),
    ),
    downgrade_rules=(
        DowngradeRule(
            metric_name="decision.accuracy",
            threshold=0.95,
            direction="above",
            target_tier=ModelTier.MEDIUM,
        ),
    ),
    min_tier_by_complexity={
        "medium":   ModelTier.MEDIUM.value,
        "high":     ModelTier.STRONG.value,
        "critical": ModelTier.STRONG.value,
    },
)

COST_OPTIMIZED_POLICY = RoutingPolicy(
    name="cost_optimized",
    description="Maximise cost efficiency; upgrade only for obvious quality failures",
    upgrade_rules=(
        UpgradeRule(
            metric_name="hallucination",
            threshold=0.55,
            direction="below",
            target_tier=ModelTier.STRONG,
            note="Only upgrade on severe hallucination",
        ),
        UpgradeRule(
            metric_name="decision.accuracy",
            threshold=0.70,
            direction="below",
            target_tier=ModelTier.MEDIUM,
            applies_to={CaseComplexity.HIGH, CaseComplexity.CRITICAL},
        ),
    ),
    downgrade_rules=(
        DowngradeRule(
            metric_name="decision.accuracy",
            threshold=0.85,
            direction="above",
            target_tier=ModelTier.FAST,
            note="Accuracy is excellent — step down to FAST tier",
        ),
    ),
    min_tier_by_complexity={
        "critical": ModelTier.MEDIUM.value,
    },
)

STRICT_POLICY = RoutingPolicy(
    name="strict",
    description="HIPAA-grade — any quality failure triggers upgrade to STRONG",
    upgrade_rules=(
        UpgradeRule(
            metric_name="hallucination",
            threshold=0.80,
            direction="below",
            target_tier=ModelTier.STRONG,
        ),
        UpgradeRule(
            metric_name="faithfulness",
            threshold=0.80,
            direction="below",
            target_tier=ModelTier.STRONG,
        ),
        UpgradeRule(
            metric_name="groundedness",
            threshold=0.75,
            direction="below",
            target_tier=ModelTier.STRONG,
        ),
        UpgradeRule(
            metric_name="decision.accuracy",
            threshold=0.85,
            direction="below",
            target_tier=ModelTier.STRONG,
        ),
        UpgradeRule(
            metric_name="reviewer_agreement.exact",
            threshold=0.80,
            direction="below",
            target_tier=ModelTier.STRONG,
        ),
    ),
    downgrade_rules=(),   # No downgrades in strict mode
    min_tier_by_complexity={
        "low":      ModelTier.MEDIUM.value,
        "medium":   ModelTier.MEDIUM.value,
        "high":     ModelTier.STRONG.value,
        "critical": ModelTier.STRONG.value,
    },
)

# Named policy registry
POLICIES: dict[str, RoutingPolicy] = {
    "default":        DEFAULT_POLICY,
    "conservative":   CONSERVATIVE_POLICY,
    "cost_optimized": COST_OPTIMIZED_POLICY,
    "strict":         STRICT_POLICY,
}


def get_policy(name: str) -> RoutingPolicy:
    policy = POLICIES.get(name)
    if policy is None:
        raise KeyError(f"Unknown routing policy '{name}'. Available: {list(POLICIES)}")
    return policy
