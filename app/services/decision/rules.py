"""
Deterministic decision rules engine.

Evaluates EvaluationResult objects according to three hard rules:

    ALL PASS  → APPROVE
    ANY FAIL  → DENY          (highest priority — one failure blocks approval)
    MISSING INFO → PEND       (no explicit failures, but unknowns remain)

Rule priority (descending):
  1. ANY_FAIL           — explicit NOT_MET criterion → DENY
  2. ALL_PASS           — all determinate criteria are MET, ≤ UNDETERMINED_TOLERANCE → APPROVE
  3. MISSING_INFO       — undetermined criteria above tolerance → PEND
  4. ALL_NOT_APPLICABLE — edge case → REFER_MEDICAL_DIRECTOR
  5. NO_CRITERIA        — nothing evaluated → REFER_MEDICAL_DIRECTOR

Additional routing:
  - LOW_CONFIDENCE fires when confidence < AUTO_DECISION_CONFIDENCE even
    after ALL_PASS, upgrading requires_human_review (not changing verdict).
  - POLICY_CONFLICT fires when multiple evaluated policies disagree on the
    verdict, adding a review flag.

The rules engine is stateless and synchronous — all async work happens
in DecisionEngine which calls it.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.services.decision.models import (
    CriterionDecision,
    DecisionRuleType,
    DecisionVerdict,
    RuleMatch,
)

logger = structlog.get_logger(__name__)

# Fraction of undetermined criteria tolerated before flipping APPROVE → PEND
UNDETERMINED_TOLERANCE = 0.10

# Minimum fraction of criteria that must be determinate to make a decision
MIN_DETERMINATE_FRACTION = 0.50

# Criterion types whose NOT_MET status is immediately blocking (fast-deny)
_BLOCKING_CRITERION_TYPES = frozenset({
    "medical_necessity",
    "safety",
    "contraindication",
    "eligibility",
    "formulary_requirement",
    "clinical_indication",
})


# ---------------------------------------------------------------------------
# Criterion status normalisation
# ---------------------------------------------------------------------------

def _normalise_status(raw: Any) -> str:
    """Return lowercase string status from CriterionMet enum or raw value."""
    if hasattr(raw, "value"):
        return raw.value.lower()
    return str(raw).lower()


def _is_blocking_type(criterion_type: str | None) -> bool:
    return (criterion_type or "").lower() in _BLOCKING_CRITERION_TYPES


# ---------------------------------------------------------------------------
# Rule evaluator
# ---------------------------------------------------------------------------

class DecisionRulesEngine:
    """
    Stateless rules engine: EvaluationResults → RuleMatch + CriterionDecisions.

    Usage:
        engine = DecisionRulesEngine()
        rule_match, criterion_decisions = engine.evaluate(evaluation_results)
    """

    def evaluate(
        self,
        evaluation_results: dict[str, Any],  # dict[str, EvaluationResult]
    ) -> tuple[RuleMatch, list[CriterionDecision]]:
        """
        Apply the three-rule PA decision logic to all evaluated policies.

        Aggregates across policies: each criterion is counted once using the
        evaluation from the highest-scoring policy that covers it.

        Returns:
            (RuleMatch, list[CriterionDecision])
        """
        if not evaluation_results:
            logger.debug("decision.rules.no_criteria")
            return (
                RuleMatch(
                    rule_type=DecisionRuleType.NO_CRITERIA,
                    verdict=DecisionVerdict.REFER_MEDICAL_DIRECTOR,
                    triggered_by="No policy criteria were evaluated.",
                ),
                [],
            )

        # Aggregate criterion decisions across all evaluated policies.
        # When the same criterion appears in multiple policies, keep the
        # evaluation with the higher confidence score.
        merged: dict[str, CriterionDecision] = {}
        for eval_result in evaluation_results.values():
            for ce in getattr(eval_result, "criteria_evaluations", []):
                cid = ce.criterion_id
                status = _normalise_status(ce.met)
                is_blocking = _is_blocking_type(
                    getattr(ce, "criterion_type", None)
                )
                cd = CriterionDecision(
                    criterion_id=cid,
                    criterion_text=ce.criterion_text or "",
                    criterion_type=getattr(ce, "criterion_type", None),
                    status=status,
                    confidence=float(ce.confidence),
                    evidence=list(ce.evidence or []),
                    policy_section=getattr(ce, "policy_section", None),
                    notes=ce.notes,
                    is_blocking=is_blocking,
                )
                # Keep the higher-confidence evaluation when duplicate
                existing = merged.get(cid)
                if existing is None or cd.confidence > existing.confidence:
                    merged[cid] = cd

        all_criteria = list(merged.values())
        rule_match = self._apply_rules(all_criteria)

        logger.debug(
            "decision.rules.evaluated",
            verdict=rule_match.verdict.value,
            rule=rule_match.rule_type.value,
            total=len(all_criteria),
            blocking=len(rule_match.blocking_criteria),
            missing=len(rule_match.missing_criteria),
        )
        return rule_match, all_criteria

    def _apply_rules(self, criteria: list[CriterionDecision]) -> RuleMatch:
        """Apply rules in priority order and return the first match."""

        # Count statuses
        met           = [c for c in criteria if c.status == "yes"]
        not_met       = [c for c in criteria if c.status == "no"]
        undetermined  = [c for c in criteria if c.status == "undetermined"]
        not_applicable = [c for c in criteria if c.status == "not_applicable"]
        determinate   = met + not_met

        total = len(criteria)

        # Edge case: all criteria are not applicable
        if total == len(not_applicable):
            return RuleMatch(
                rule_type=DecisionRuleType.ALL_NOT_APPLICABLE,
                verdict=DecisionVerdict.REFER_MEDICAL_DIRECTOR,
                triggered_by=(
                    "All evaluated criteria are marked not applicable. "
                    "Manual review required to determine applicable policy."
                ),
            )

        # Edge case: not enough determinate criteria for a decision
        determinate_fraction = len(determinate) / max(total - len(not_applicable), 1)
        if determinate_fraction < MIN_DETERMINATE_FRACTION and len(undetermined) > 0:
            return RuleMatch(
                rule_type=DecisionRuleType.MISSING_INFO,
                verdict=DecisionVerdict.PEND_FOR_INFO,
                triggered_by=(
                    f"Only {len(determinate)}/{total - len(not_applicable)} criteria "
                    "are determinate. Insufficient evidence to make a decision."
                ),
                missing_criteria=[c.criterion_id for c in undetermined],
            )

        # ── Rule 1: ANY FAIL → DENY ───────────────────────────────────────
        if not_met:
            # Separate blocking (hard) failures from soft failures
            blocking = [c for c in not_met if c.is_blocking]
            blocking_ids = [c.criterion_id for c in not_met]
            blocking_texts = [c.criterion_text[:80] for c in not_met[:3]]

            trigger = (
                f"{len(not_met)} criterion/criteria not met"
                + (f" ({len(blocking)} blocking)" if blocking else "")
                + ": "
                + "; ".join(blocking_texts)
                + ("..." if len(not_met) > 3 else "")
            )
            return RuleMatch(
                rule_type=DecisionRuleType.ANY_FAIL,
                verdict=DecisionVerdict.DENY,
                triggered_by=trigger,
                blocking_criteria=blocking_ids,
            )

        # ── Rule 2: ALL PASS → APPROVE ────────────────────────────────────
        undetermined_fraction = (
            len(undetermined) / max(total - len(not_applicable), 1)
        )
        if len(met) > 0 and undetermined_fraction <= UNDETERMINED_TOLERANCE:
            return RuleMatch(
                rule_type=DecisionRuleType.ALL_PASS,
                verdict=DecisionVerdict.APPROVE,
                triggered_by=(
                    f"All {len(met)} applicable criteria met"
                    + (
                        f" ({len(undetermined)} undetermined, within "
                        f"{UNDETERMINED_TOLERANCE:.0%} tolerance)"
                        if undetermined else ""
                    )
                    + "."
                ),
            )

        # ── Rule 3: MISSING INFO → PEND ───────────────────────────────────
        if undetermined:
            return RuleMatch(
                rule_type=DecisionRuleType.MISSING_INFO,
                verdict=DecisionVerdict.PEND_FOR_INFO,
                triggered_by=(
                    f"{len(undetermined)} of {total - len(not_applicable)} "
                    "applicable criteria are undetermined. "
                    "Additional clinical information required."
                ),
                missing_criteria=[c.criterion_id for c in undetermined],
            )

        # ── Fallback (met=0, undetermined=0) → cannot approve ─────────────
        return RuleMatch(
            rule_type=DecisionRuleType.NO_CRITERIA,
            verdict=DecisionVerdict.REFER_MEDICAL_DIRECTOR,
            triggered_by="No criteria were met and no explicit failures — medical director review required.",
        )

    def check_policy_conflict(
        self,
        evaluation_results: dict[str, Any],
    ) -> bool:
        """
        Return True if multiple policies produce conflicting verdicts.

        Used to flag cases for human review even when a single verdict
        can be determined from the aggregate.
        """
        if len(evaluation_results) < 2:
            return False

        per_policy_verdicts: list[DecisionVerdict] = []
        for eval_result in evaluation_results.values():
            criteria_evals = getattr(eval_result, "criteria_evaluations", [])
            if not criteria_evals:
                continue
            has_fail = any(_normalise_status(ce.met) == "no" for ce in criteria_evals)
            has_undet = any(_normalise_status(ce.met) == "undetermined" for ce in criteria_evals)
            if has_fail:
                per_policy_verdicts.append(DecisionVerdict.DENY)
            elif has_undet:
                per_policy_verdicts.append(DecisionVerdict.PEND_FOR_INFO)
            else:
                per_policy_verdicts.append(DecisionVerdict.APPROVE)

        unique = set(per_policy_verdicts)
        return len(unique) > 1
