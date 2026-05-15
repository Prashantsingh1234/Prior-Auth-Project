"""
Multi-factor confidence calculator for the decision engine.

Confidence represents the system's certainty that the verdict is correct,
not the clinical validity of the underlying evidence.

Factors (weights sum to 1.0):
  ┌────────────────────────────────┬────────┐
  │ Factor                         │ Weight │
  ├────────────────────────────────┼────────┤
  │ Criterion confidence avg       │  0.40  │
  │ Coverage score                 │  0.25  │
  │ Evidence quality score         │  0.20  │
  │ Extraction confidence          │  0.15  │
  └────────────────────────────────┴────────┘

Penalties (subtracted from weighted score):
  - Undetermined fraction > 20%  → -0.10
  - Undetermined fraction > 40%  → -0.15 (additional)
  - Missing evidence fraction > 30% → -0.05
  - Cross-policy conflict         → -0.08
  - Low extraction confidence     → -0.05

Bonuses (added to weighted score):
  - All criteria unanimous (all MET or all NOT_MET) → +0.05
  - High evidence quality (> 80%) → +0.03

Final score is clamped to [0.0, 1.0].
"""

from __future__ import annotations

import math
from typing import Any

from app.services.decision.models import (
    ConfidenceBreakdown,
    ConfidenceFlag,
    CriterionDecision,
    DecisionRuleType,
    DecisionVerdict,
)

# Component weights
_CRITERION_CONF_WEIGHT = 0.40
_COVERAGE_WEIGHT       = 0.25
_EVIDENCE_WEIGHT       = 0.20
_EXTRACTION_WEIGHT     = 0.15

# Penalty magnitudes
_PENALTY_UNDETERMINED_MODERATE = 0.10   # undetermined > 20%
_PENALTY_UNDETERMINED_HIGH     = 0.15   # undetermined > 40%
_PENALTY_MISSING_EVIDENCE      = 0.05   # > 30% of determined criteria lack evidence
_PENALTY_POLICY_CONFLICT       = 0.08
_PENALTY_LOW_EXTRACTION        = 0.05   # extraction confidence < 0.60

# Bonus magnitudes
_BONUS_UNANIMOUS               = 0.05   # all criteria agree
_BONUS_HIGH_EVIDENCE           = 0.03   # > 80% of determined criteria have evidence

# Thresholds
_LOW_EXTRACTION_THRESHOLD      = 0.60
_AUTO_DECISION_THRESHOLD       = 0.80   # below this → requires_human_review = True


class ConfidenceCalculator:
    """
    Computes a calibrated confidence score from rule engine outputs.

    Stateless — one instance can be reused across many evaluations.
    """

    def calculate(
        self,
        *,
        criterion_decisions: list[CriterionDecision],
        verdict: DecisionVerdict,
        rule_type: DecisionRuleType,
        extraction_confidence: float,
        policy_conflict: bool,
    ) -> ConfidenceBreakdown:
        """
        Compute confidence for the given decision.

        Parameters
        ----------
        criterion_decisions:
            All CriterionDecision objects from the rules engine.
        verdict:
            The verdict determined by the rules engine.
        rule_type:
            Which rule fired.
        extraction_confidence:
            Average OCR/extraction confidence from ExtractedEntities.
        policy_conflict:
            True when multiple evaluated policies disagree.
        """
        # Categorise criteria (exclude not_applicable from denominator)
        applicable = [c for c in criterion_decisions if c.status != "not_applicable"]
        met         = [c for c in applicable if c.status == "yes"]
        not_met     = [c for c in applicable if c.status == "no"]
        undetermined = [c for c in applicable if c.status == "undetermined"]
        determined  = met + not_met

        total_applicable = len(applicable)
        total_determined = len(determined)
        flags: list[ConfidenceFlag] = []

        # ------------------------------------------------------------------
        # Component 1: criterion confidence average
        # Only use determinate criteria (undetermined ones have unreliable conf)
        # ------------------------------------------------------------------
        if determined:
            crit_conf_avg = sum(c.confidence for c in determined) / len(determined)
        elif applicable:
            # All undetermined — use a deflated average
            crit_conf_avg = sum(c.confidence for c in applicable) / len(applicable) * 0.60
        else:
            crit_conf_avg = 0.30  # no criteria at all

        # ------------------------------------------------------------------
        # Component 2: coverage score
        # Fraction of applicable criteria that have a determinate answer
        # ------------------------------------------------------------------
        if total_applicable:
            coverage_score = total_determined / total_applicable
        else:
            coverage_score = 0.0

        # ------------------------------------------------------------------
        # Component 3: evidence quality
        # Fraction of determined criteria backed by evidence quotes
        # ------------------------------------------------------------------
        if total_determined:
            with_evidence = sum(1 for c in determined if c.evidence)
            evidence_quality = with_evidence / total_determined
            criteria_with_evidence_count = with_evidence
        else:
            evidence_quality = 0.0
            criteria_with_evidence_count = 0

        # ------------------------------------------------------------------
        # Component 4: extraction confidence (passed in)
        # Clamp to a safe range
        # ------------------------------------------------------------------
        extraction_conf = max(0.0, min(1.0, extraction_confidence))

        # ------------------------------------------------------------------
        # Weighted base score
        # ------------------------------------------------------------------
        base = (
            crit_conf_avg   * _CRITERION_CONF_WEIGHT
            + coverage_score  * _COVERAGE_WEIGHT
            + evidence_quality * _EVIDENCE_WEIGHT
            + extraction_conf  * _EXTRACTION_WEIGHT
        )

        # ------------------------------------------------------------------
        # Penalties
        # ------------------------------------------------------------------
        penalties = 0.0

        undetermined_fraction = (
            len(undetermined) / total_applicable if total_applicable else 0.0
        )
        if undetermined_fraction > 0.40:
            penalties += _PENALTY_UNDETERMINED_HIGH
            flags.append(ConfidenceFlag.UNDETERMINED_CRITERIA)
        elif undetermined_fraction > 0.20:
            penalties += _PENALTY_UNDETERMINED_MODERATE
            flags.append(ConfidenceFlag.UNDETERMINED_CRITERIA)

        if total_determined > 0:
            missing_evidence_frac = 1.0 - (criteria_with_evidence_count / total_determined)
            if missing_evidence_frac > 0.30:
                penalties += _PENALTY_MISSING_EVIDENCE
                flags.append(ConfidenceFlag.MISSING_EVIDENCE)

        if policy_conflict:
            penalties += _PENALTY_POLICY_CONFLICT
            flags.append(ConfidenceFlag.CROSS_POLICY_CONFLICT)

        if extraction_conf < _LOW_EXTRACTION_THRESHOLD:
            penalties += _PENALTY_LOW_EXTRACTION
            flags.append(ConfidenceFlag.LOW_EXTRACTION_CONFIDENCE)

        # Edge case: only one criterion evaluated
        if len(applicable) == 1:
            flags.append(ConfidenceFlag.SINGLE_CRITERION)

        # ------------------------------------------------------------------
        # Bonuses
        # ------------------------------------------------------------------
        bonuses = 0.0

        if determined and not undetermined:
            # All applicable criteria are determinate (unanimous)
            bonuses += _BONUS_UNANIMOUS
            flags.append(ConfidenceFlag.HIGH_CRITERION_AGREEMENT)

        if total_determined > 0 and (criteria_with_evidence_count / total_determined) > 0.80:
            bonuses += _BONUS_HIGH_EVIDENCE
            flags.append(ConfidenceFlag.HIGH_EVIDENCE_QUALITY)

        # Partial coverage flag (informational only)
        if 0 < coverage_score < 0.80:
            flags.append(ConfidenceFlag.PARTIAL_COVERAGE)

        # ------------------------------------------------------------------
        # For edge-case rules, floor the confidence to communicate uncertainty
        # ------------------------------------------------------------------
        if rule_type in (
            DecisionRuleType.NO_CRITERIA,
            DecisionRuleType.ALL_NOT_APPLICABLE,
            DecisionRuleType.POLICY_CONFLICT,
        ):
            base = min(base, 0.40)

        final = max(0.0, min(1.0, base - penalties + bonuses))

        return ConfidenceBreakdown(
            final_score=round(final, 4),
            criterion_confidence_avg=round(crit_conf_avg, 4),
            coverage_score=round(coverage_score, 4),
            evidence_quality_score=round(evidence_quality, 4),
            extraction_confidence=round(extraction_conf, 4),
            penalties=round(penalties, 4),
            bonuses=round(bonuses, 4),
            flags=flags,
            total_criteria=len(criterion_decisions),
            met_count=len(met),
            not_met_count=len(not_met),
            undetermined_count=len(undetermined),
            not_applicable_count=len([c for c in criterion_decisions if c.status == "not_applicable"]),
            criteria_with_evidence=criteria_with_evidence_count,
        )

    @staticmethod
    def requires_human_review(
        breakdown: ConfidenceBreakdown,
        verdict: DecisionVerdict,
    ) -> tuple[bool, str | None]:
        """
        Determine whether a human reviewer should see this decision.

        Returns (requires_review, reason_string).
        """
        score = breakdown.final_score

        if score < _AUTO_DECISION_THRESHOLD:
            return True, f"AI confidence {score:.0%} below {_AUTO_DECISION_THRESHOLD:.0%} auto-decision threshold"

        if ConfidenceFlag.CROSS_POLICY_CONFLICT in breakdown.flags:
            return True, "Conflicting signals across evaluated policies"

        if breakdown.undetermined_count > 0 and verdict == DecisionVerdict.APPROVE:
            return True, f"{breakdown.undetermined_count} criteria remain undetermined"

        if ConfidenceFlag.LOW_EXTRACTION_CONFIDENCE in breakdown.flags:
            return True, "Low OCR/extraction confidence — clinical data may be incomplete"

        return False, None
