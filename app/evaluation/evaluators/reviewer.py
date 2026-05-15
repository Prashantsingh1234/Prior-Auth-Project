"""
Reviewer agreement evaluator.

Measures how often the AI system's decision matches the human reviewer's
decision on the same case.  This is the gold-standard metric for a PA
automation system because it directly measures clinical alignment.

Metrics produced:
  reviewer_agreement.exact        — simple percentage agreement (0.0–1.0)
  reviewer_agreement.kappa        — Cohen's kappa (−1.0–1.0, mapped to 0.0–1.0)
  reviewer_agreement.weighted     — weighted kappa with ordered label distance

Label ordering for weighted kappa: APPROVE > PEND > DENY > ESCALATE
(adjacent disagreements count less than APPROVE↔DENY)

Thresholds:
  exact  ≥ 0.80  (80% agreement)
  kappa  ≥ 0.60  (substantial agreement on Landis-Koch scale)

Note: kappa requires a batch of predictions (not a single case).
For single-case evaluation, only exact agreement is returned.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import structlog

from app.evaluation.evaluators.base import BaseEvaluator, EvalInput
from app.evaluation.models import EvalMetric

logger = structlog.get_logger(__name__)

_EXACT_THRESHOLD  = 0.80
_KAPPA_THRESHOLD  = 0.60

# Ordered labels for weighted kappa penalty calculation
_LABEL_ORDER = ["APPROVE", "PEND", "DENY", "ESCALATE"]


def _label_distance(a: str, b: str) -> int:
    """Ordinal distance between two verdict labels (0 = same)."""
    try:
        return abs(_LABEL_ORDER.index(a.upper()) - _LABEL_ORDER.index(b.upper()))
    except ValueError:
        return 1 if a.upper() != b.upper() else 0


def _cohens_kappa(ai_labels: list[str], human_labels: list[str]) -> float:
    """
    Compute Cohen's kappa for two lists of categorical labels.

    Returns a value in [−1, 1].  Caller maps to [0, 1] for the metric.
    """
    if len(ai_labels) != len(human_labels) or not ai_labels:
        return 0.0

    n = len(ai_labels)
    all_labels = list(set(ai_labels + human_labels))

    # Observed agreement
    p_o = sum(1 for a, h in zip(ai_labels, human_labels) if a == h) / n

    # Expected agreement (product of marginal frequencies)
    ai_counts   = Counter(ai_labels)
    human_counts = Counter(human_labels)
    p_e = sum(
        (ai_counts.get(lbl, 0) / n) * (human_counts.get(lbl, 0) / n)
        for lbl in all_labels
    )

    if p_e == 1.0:
        return 1.0
    return (p_o - p_e) / (1.0 - p_e)


def _weighted_kappa(ai_labels: list[str], human_labels: list[str]) -> float:
    """
    Linear-weighted kappa using _LABEL_ORDER distances.

    Penalises APPROVE↔DENY more than APPROVE↔PEND.
    """
    if len(ai_labels) != len(human_labels) or not ai_labels:
        return 0.0

    n = len(ai_labels)
    max_dist = len(_LABEL_ORDER) - 1  # normalisation constant

    # Observed weighted disagreement
    obs_dis = sum(
        _label_distance(a, h) / max_dist
        for a, h in zip(ai_labels, human_labels)
    ) / n

    # Expected weighted disagreement
    all_labels = _LABEL_ORDER
    ai_counts    = Counter(ai_labels)
    human_counts = Counter(human_labels)
    exp_dis = sum(
        (ai_counts.get(i, 0) / n) * (human_counts.get(j, 0) / n)
        * (_label_distance(i, j) / max_dist)
        for i in all_labels
        for j in all_labels
    )

    if exp_dis == 0.0:
        return 1.0
    return 1.0 - (obs_dis / exp_dis)


@dataclass
class ReviewerAgreementState:
    """
    Accumulates predictions across multiple calls for batch kappa computation.
    One instance per model per evaluation run.
    """
    ai_verdicts:     list[str] = field(default_factory=list)
    human_verdicts:  list[str] = field(default_factory=list)
    exact_agreements: int = 0

    def record(self, ai_verdict: str, human_verdict: str) -> None:
        self.ai_verdicts.append(ai_verdict.upper())
        self.human_verdicts.append(human_verdict.upper())
        if ai_verdict.upper() == human_verdict.upper():
            self.exact_agreements += 1

    @property
    def exact_agreement(self) -> float:
        n = len(self.ai_verdicts)
        return self.exact_agreements / n if n else 0.0

    def kappa(self) -> float:
        return max(0.0, _cohens_kappa(self.ai_verdicts, self.human_verdicts))

    def weighted_kappa(self) -> float:
        return max(0.0, _weighted_kappa(self.ai_verdicts, self.human_verdicts))


class ReviewerAgreementEvaluator(BaseEvaluator):
    """
    Per-case reviewer agreement evaluator.

    For single-case evaluation returns exact agreement only.
    Call `batch_evaluate()` with a shared `ReviewerAgreementState` to
    get kappa across many cases.
    """

    name = "reviewer_agreement"

    async def evaluate(self, inp: EvalInput) -> list[EvalMetric]:
        if not inp.actual_verdict or not inp.reviewer_verdict:
            return [EvalMetric(
                name="reviewer_agreement.exact",
                value=0.0,
                threshold=_EXACT_THRESHOLD,
                details={"skipped": "missing actual_verdict or reviewer_verdict"},
            )]

        exact = 1.0 if inp.actual_verdict.upper() == inp.reviewer_verdict.upper() else 0.0
        dist  = _label_distance(inp.actual_verdict, inp.reviewer_verdict)

        return [EvalMetric(
            name="reviewer_agreement.exact",
            value=exact,
            threshold=_EXACT_THRESHOLD,
            details={
                "ai_verdict":       inp.actual_verdict,
                "reviewer_verdict": inp.reviewer_verdict,
                "label_distance":   dist,
            },
        )]

    @staticmethod
    def compute_batch_metrics(state: ReviewerAgreementState) -> list[EvalMetric]:
        """
        Compute kappa metrics from an accumulated ReviewerAgreementState.
        Call this at the end of a pipeline run after all cases are scored.
        """
        exact   = state.exact_agreement
        kappa   = state.kappa()
        wkappa  = state.weighted_kappa()

        return [
            EvalMetric(
                name="reviewer_agreement.exact",
                value=round(exact, 4),
                threshold=_EXACT_THRESHOLD,
                details={"n": len(state.ai_verdicts)},
            ),
            EvalMetric(
                name="reviewer_agreement.cohens_kappa",
                value=round(kappa, 4),
                threshold=_KAPPA_THRESHOLD,
                weight=1.5,
                details={
                    "raw_kappa": round(_cohens_kappa(state.ai_verdicts, state.human_verdicts), 4),
                    "n": len(state.ai_verdicts),
                },
            ),
            EvalMetric(
                name="reviewer_agreement.weighted_kappa",
                value=round(wkappa, 4),
                threshold=_KAPPA_THRESHOLD,
                weight=1.5,
                details={"n": len(state.ai_verdicts)},
            ),
        ]
