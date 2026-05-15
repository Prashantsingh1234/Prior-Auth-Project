"""
Decision accuracy evaluator.

Measures how accurately the AI decision engine classifies PA cases against
ground-truth labels.  Produces a full multi-class classification report
across three verdict classes: APPROVE, DENY, PEND.

Metrics produced:
  decision.accuracy          — overall fraction correct
  decision.precision_macro   — macro-averaged precision
  decision.recall_macro      — macro-averaged recall
  decision.f1_macro          — macro-averaged F1
  decision.approve_f1        — per-class F1 for APPROVE
  decision.deny_f1           — per-class F1 for DENY
  decision.pend_f1           — per-class F1 for PEND

Uses sklearn when available; falls back to manual computation otherwise.

Thresholds:
  accuracy  ≥ 0.85
  f1_macro  ≥ 0.80
  deny_f1   ≥ 0.85  (denials have higher stakes — false negatives cost patient access)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import structlog

from app.evaluation.evaluators.base import BaseEvaluator, EvalInput
from app.evaluation.models import EvalMetric

logger = structlog.get_logger(__name__)

_ACCURACY_THRESHOLD   = 0.85
_F1_MACRO_THRESHOLD   = 0.80
_DENY_F1_THRESHOLD    = 0.85
_APPROVE_F1_THRESHOLD = 0.80
_PEND_F1_THRESHOLD    = 0.75

_LABELS = ["APPROVE", "DENY", "PEND"]


def _safe_div(num: float, den: float) -> float:
    return num / den if den > 0 else 0.0


def _per_class_metrics(
    y_true: list[str],
    y_pred: list[str],
    label: str,
) -> tuple[float, float, float]:
    """Returns (precision, recall, f1) for a single class label."""
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
    precision = _safe_div(tp, tp + fp)
    recall    = _safe_div(tp, tp + fn)
    f1        = _safe_div(2 * precision * recall, precision + recall)
    return precision, recall, f1


@dataclass
class DecisionAccuracyState:
    """
    Accumulates predictions for a batch of cases.

    Use record() once per case, then call compute_metrics() at the end.
    """
    y_true: list[str] = field(default_factory=list)
    y_pred: list[str] = field(default_factory=list)
    case_ids: list[str] = field(default_factory=list)

    def record(self, true_verdict: str, pred_verdict: str, case_id: str = "") -> None:
        self.y_true.append(true_verdict.upper())
        self.y_pred.append(pred_verdict.upper())
        self.case_ids.append(case_id)

    def compute_metrics(self) -> list[EvalMetric]:
        if not self.y_true:
            return []

        # Try sklearn first for a complete classification report
        try:
            return self._sklearn_metrics()
        except ImportError:
            pass

        return self._manual_metrics()

    def _sklearn_metrics(self) -> list[EvalMetric]:
        from sklearn.metrics import (
            accuracy_score,
            precision_recall_fscore_support,
            classification_report,
        )

        accuracy = accuracy_score(self.y_true, self.y_pred)
        p_macro, r_macro, f1_macro, _ = precision_recall_fscore_support(
            self.y_true, self.y_pred,
            average="macro",
            labels=_LABELS,
            zero_division=0,
        )
        per_class_p, per_class_r, per_class_f1, _ = precision_recall_fscore_support(
            self.y_true, self.y_pred,
            average=None,
            labels=_LABELS,
            zero_division=0,
        )
        label_f1 = {lbl: float(per_class_f1[i]) for i, lbl in enumerate(_LABELS)}

        return _build_metrics(
            accuracy=float(accuracy),
            precision_macro=float(p_macro),
            recall_macro=float(r_macro),
            f1_macro=float(f1_macro),
            per_label_f1=label_f1,
            n=len(self.y_true),
        )

    def _manual_metrics(self) -> list[EvalMetric]:
        n = len(self.y_true)
        accuracy = sum(1 for t, p in zip(self.y_true, self.y_pred) if t == p) / n

        precisions, recalls, f1s = [], [], []
        label_f1: dict[str, float] = {}
        for lbl in _LABELS:
            p, r, f = _per_class_metrics(self.y_true, self.y_pred, lbl)
            precisions.append(p)
            recalls.append(r)
            f1s.append(f)
            label_f1[lbl] = f

        p_macro  = sum(precisions) / len(precisions)
        r_macro  = sum(recalls) / len(recalls)
        f1_macro = sum(f1s) / len(f1s)

        return _build_metrics(
            accuracy=accuracy,
            precision_macro=p_macro,
            recall_macro=r_macro,
            f1_macro=f1_macro,
            per_label_f1=label_f1,
            n=n,
        )


def _build_metrics(
    *,
    accuracy: float,
    precision_macro: float,
    recall_macro: float,
    f1_macro: float,
    per_label_f1: dict[str, float],
    n: int,
) -> list[EvalMetric]:
    return [
        EvalMetric(
            name="decision.accuracy",
            value=round(accuracy, 4),
            threshold=_ACCURACY_THRESHOLD,
            weight=2.0,
            details={"n": n},
        ),
        EvalMetric(
            name="decision.precision_macro",
            value=round(precision_macro, 4),
            threshold=_F1_MACRO_THRESHOLD,
            details={"n": n},
        ),
        EvalMetric(
            name="decision.recall_macro",
            value=round(recall_macro, 4),
            threshold=_F1_MACRO_THRESHOLD,
            details={"n": n},
        ),
        EvalMetric(
            name="decision.f1_macro",
            value=round(f1_macro, 4),
            threshold=_F1_MACRO_THRESHOLD,
            weight=1.5,
            details={"n": n},
        ),
        EvalMetric(
            name="decision.approve_f1",
            value=round(per_label_f1.get("APPROVE", 0.0), 4),
            threshold=_APPROVE_F1_THRESHOLD,
            details={"label": "APPROVE"},
        ),
        EvalMetric(
            name="decision.deny_f1",
            value=round(per_label_f1.get("DENY", 0.0), 4),
            threshold=_DENY_F1_THRESHOLD,
            weight=2.0,  # denial accuracy is higher-stakes
            details={"label": "DENY"},
        ),
        EvalMetric(
            name="decision.pend_f1",
            value=round(per_label_f1.get("PEND", 0.0), 4),
            threshold=_PEND_F1_THRESHOLD,
            details={"label": "PEND"},
        ),
    ]


class DecisionAccuracyEvaluator(BaseEvaluator):
    """
    Single-case decision accuracy evaluator.

    For batch metrics (precision/recall/F1) use DecisionAccuracyState
    directly and call compute_metrics() after recording all cases.
    """

    name = "decision_accuracy"

    async def evaluate(self, inp: EvalInput) -> list[EvalMetric]:
        if not inp.expected_verdict or not inp.actual_verdict:
            return [EvalMetric(
                name="decision.accuracy",
                value=0.0,
                threshold=_ACCURACY_THRESHOLD,
                weight=2.0,
                details={"skipped": "missing expected_verdict or actual_verdict"},
            )]

        correct = inp.actual_verdict.upper() == inp.expected_verdict.upper()
        dist = 0 if correct else abs(
            _LABELS.index(inp.actual_verdict.upper()) if inp.actual_verdict.upper() in _LABELS else 1
        )

        return [EvalMetric(
            name="decision.accuracy",
            value=1.0 if correct else 0.0,
            threshold=_ACCURACY_THRESHOLD,
            weight=2.0,
            details={
                "expected": inp.expected_verdict,
                "actual":   inp.actual_verdict,
                "label_distance": dist,
            },
        )]
