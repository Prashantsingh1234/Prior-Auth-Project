"""
Evaluator-driven model router.

The router selects which model to use for a given PA case based on:
  1. Case complexity  — directly maps to a minimum model tier
  2. Current model performance — rolling-window metrics from the metrics store
  3. Active routing policy — which metrics trigger up/downgrade

Routing algorithm (in order of precedence):
  1. Apply policy.min_tier_by_complexity — hard floor
  2. Check upgrade rules against current performance metrics
     → any firing rule triggers upgrade to target_tier
  3. Check downgrade rules
     → any firing rule triggers downgrade if not blocked by complexity floor
  4. Fall back to domain default model if no rule fires

The router is stateless at call time — it reads a ModelPerformanceSummary
snapshot from the metrics store on each call.  The store updates summaries
on a configurable schedule (default: every 15 minutes).

Thread-safety: fully safe — all state is immutable or read-only at routing time.
"""

from __future__ import annotations

import structlog

from app.evaluation.models import (
    CaseComplexity,
    EvalDomain,
    ModelPerformanceSummary,
    ModelTier,
    RoutingDecision,
    RoutingReason,
)
from app.evaluation.routing.policy import RoutingPolicy, get_policy
from app.evaluation.routing.registry import ModelInfo, ModelRegistry, get_model_registry

logger = structlog.get_logger(__name__)


class EvaluatorDrivenRouter:
    """
    Routes PA cases to the appropriate model based on live evaluation metrics.

    Parameters
    ----------
    policy_name:
        Name of the active routing policy (see routing/policy.py).
    registry:
        Model registry.  Defaults to the singleton from registry.py.
    """

    def __init__(
        self,
        policy_name: str = "default",
        registry: ModelRegistry | None = None,
    ) -> None:
        self._policy: RoutingPolicy = get_policy(policy_name)
        self._registry: ModelRegistry = registry or get_model_registry()

    # ------------------------------------------------------------------
    # Primary routing entry point
    # ------------------------------------------------------------------

    def route(
        self,
        domain: EvalDomain,
        complexity: CaseComplexity,
        performance_summaries: dict[str, ModelPerformanceSummary],
    ) -> RoutingDecision:
        """
        Select the best model for a given case.

        Parameters
        ----------
        domain:
            The pipeline domain (EXTRACTION, REASONING, etc.)
        complexity:
            Estimated case complexity.
        performance_summaries:
            Latest rolling-window performance for each candidate model.
            Keys are model_ids.  May be empty (falls back to registry defaults).

        Returns
        -------
        RoutingDecision
            Contains the chosen model_id, reason, and per-model scores.
        """
        # 1. Determine minimum required tier from policy
        min_tier = self._policy.min_tier(complexity)

        # 2. Score all candidates in registry
        candidates = self._registry.models_for_domain(domain)
        if not candidates:
            candidates = self._registry.all_models()

        scores = self._score_candidates(candidates, performance_summaries)

        # 3. Start from the domain default model
        default_model = self._registry.default_model(domain) or candidates[0]
        selected_model = default_model
        selected_tier  = selected_model.tier
        reason         = RoutingReason.DEFAULT

        # 4. Apply policy upgrade rules against current best model's metrics
        if selected_model.model_id in performance_summaries:
            perf = performance_summaries[selected_model.model_id]
            flat_metrics = _flatten_performance(perf)

            upgrade_rule = self._policy.evaluate_upgrades(flat_metrics, complexity)
            if upgrade_rule:
                upgraded = self._best_model_at_tier(
                    upgrade_rule.target_tier, domain, scores
                )
                if upgraded:
                    selected_model = upgraded
                    selected_tier  = upgraded.tier
                    reason         = RoutingReason.PERFORMANCE_UPGRADE
                    logger.info(
                        "router.upgrade",
                        rule=upgrade_rule.note,
                        from_model=default_model.model_id,
                        to_model=upgraded.model_id,
                    )

            elif not upgrade_rule:
                downgrade_rule = self._policy.evaluate_downgrades(flat_metrics)
                if downgrade_rule and (
                    min_tier is None
                    or _tier_rank(downgrade_rule.target_tier) >= _tier_rank(min_tier)
                ):
                    downgraded = self._best_model_at_tier(
                        downgrade_rule.target_tier, domain, scores
                    )
                    if downgraded:
                        selected_model = downgraded
                        selected_tier  = downgraded.tier
                        reason         = RoutingReason.PERFORMANCE_DOWNGRADE
                        logger.info(
                            "router.downgrade",
                            rule=downgrade_rule.note,
                            from_model=default_model.model_id,
                            to_model=downgraded.model_id,
                        )

        # 5. Enforce complexity floor
        if min_tier and _tier_rank(selected_tier) < _tier_rank(min_tier):
            floored = self._best_model_at_tier(min_tier, domain, scores)
            if floored:
                prev = selected_model.model_id
                selected_model = floored
                reason         = RoutingReason.COMPLEXITY_UPGRADE
                logger.info(
                    "router.complexity_floor",
                    complexity=complexity.value,
                    min_tier=min_tier.value,
                    from_model=prev,
                    to_model=floored.model_id,
                )

        return RoutingDecision(
            model_id=selected_model.model_id,
            model_tier=selected_model.tier,
            reason=reason,
            case_complexity=complexity,
            confidence=scores.get(selected_model.model_id, 0.5),
            scores=scores,
            policy_name=self._policy.name,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _score_candidates(
        self,
        candidates: list[ModelInfo],
        performance: dict[str, ModelPerformanceSummary],
    ) -> dict[str, float]:
        """
        Compute a composite routing score for each candidate model.

        Score = 0.7 × quality + 0.3 × (1 - normalised_latency)
        Falls back to 0.5 for models with no performance history.
        """
        scores: dict[str, float] = {}

        # Normalise latency across candidates
        latencies = [
            performance[m.model_id].avg_latency_ms
            for m in candidates
            if m.model_id in performance
        ]
        max_latency = max(latencies, default=1.0) or 1.0

        for model in candidates:
            perf = performance.get(model.model_id)
            if perf is None:
                scores[model.model_id] = 0.50
                continue

            quality  = perf.composite_quality_score
            norm_lat = perf.avg_latency_ms / max_latency
            scores[model.model_id] = round(0.70 * quality + 0.30 * (1.0 - norm_lat), 4)

        return scores

    def _best_model_at_tier(
        self,
        tier: ModelTier,
        domain: EvalDomain,
        scores: dict[str, float],
    ) -> ModelInfo | None:
        """Return the highest-scored model at a given tier for a domain."""
        candidates = [
            m for m in self._registry.models_for_domain(domain)
            if m.tier == tier
        ]
        if not candidates:
            candidates = self._registry.models_for_tier(tier)

        if not candidates:
            return None

        return max(candidates, key=lambda m: scores.get(m.model_id, 0.0))

    def switch_policy(self, policy_name: str) -> None:
        """Hot-swap the routing policy (e.g., on an incident)."""
        self._policy = get_policy(policy_name)
        logger.info("router.policy_switched", policy=policy_name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TIER_RANK = {ModelTier.FAST: 0, ModelTier.MEDIUM: 1, ModelTier.STRONG: 2}


def _tier_rank(tier: ModelTier) -> int:
    return _TIER_RANK.get(tier, 0)


def _flatten_performance(perf: ModelPerformanceSummary) -> dict[str, float]:
    """Convert a ModelPerformanceSummary to a flat metric dict for policy evaluation."""
    return {
        "hallucination":             1.0 - perf.hallucination_rate,
        "faithfulness":              perf.faithfulness_score,
        "groundedness":              perf.groundedness_score,
        "answer_relevancy":          perf.answer_relevancy,
        "retrieval.context_precision": perf.retrieval_precision,
        "retrieval.context_recall":    perf.retrieval_recall,
        "reviewer_agreement.exact":  perf.reviewer_agreement,
        "decision.accuracy":         perf.decision_accuracy,
        "json_validation":           perf.json_validation_rate,
        "escalation_rate":           perf.escalation_rate,
        "fallback_rate":             perf.fallback_rate,
        "error_rate":                perf.error_rate,
    }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_router_instance: EvaluatorDrivenRouter | None = None


def get_router(policy_name: str = "default") -> EvaluatorDrivenRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = EvaluatorDrivenRouter(policy_name=policy_name)
    return _router_instance
