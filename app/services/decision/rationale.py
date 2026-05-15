"""
Structured rationale formatter for the decision engine.

Produces ordered, human-readable rationale lines that explain:
  1. The verdict and the rule that triggered it
  2. Criteria that supported the decision (MET)
  3. Criteria that blocked the decision (NOT_MET)
  4. Criteria requiring more information (UNDETERMINED)
  5. Confidence score interpretation
  6. Override justification (if applicable)

Output is a list[str] suitable for PARecommendation.rationale.
Each line is one complete sentence — reviewers and auditors can read
the list top-to-bottom to understand the full decision chain.
"""

from __future__ import annotations

from app.services.decision.models import (
    ConfidenceBreakdown,
    ConfidenceFlag,
    CriterionDecision,
    DecisionRuleType,
    DecisionVerdict,
    OverrideRequest,
    RuleMatch,
)

# Maximum criteria to list individually in rationale
_MAX_CRITERIA_IN_RATIONALE = 5

# Confidence bands for human-readable interpretation
_CONFIDENCE_BANDS = [
    (0.90, "very high"),
    (0.80, "high"),
    (0.70, "moderate-high"),
    (0.60, "moderate"),
    (0.40, "low"),
    (0.00, "very low"),
]


def _confidence_label(score: float) -> str:
    for threshold, label in _CONFIDENCE_BANDS:
        if score >= threshold:
            return label
    return "very low"


def _truncate(text: str, max_len: int = 100) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 1].rstrip() + "…"


class RationaleFormatter:
    """
    Builds structured rationale lines from decision engine outputs.

    Stateless — one instance is reusable.
    """

    def format(
        self,
        *,
        verdict: DecisionVerdict,
        rule_match: RuleMatch,
        criterion_decisions: list[CriterionDecision],
        confidence: ConfidenceBreakdown,
        override_request: OverrideRequest | None = None,
    ) -> tuple[list[str], list[str], list[str], list[str]]:
        """
        Produce rationale components.

        Returns:
            (rationale_lines, supporting_criteria, denying_criteria, evidence_references)
        """
        lines: list[str] = []
        supporting: list[str] = []
        denying: list[str] = []
        evidence: list[str] = []

        # ------------------------------------------------------------------
        # 1. Verdict summary line
        # ------------------------------------------------------------------
        lines.append(self._verdict_summary(verdict, rule_match, confidence))

        # ------------------------------------------------------------------
        # 2. Criteria breakdown
        # ------------------------------------------------------------------
        met_criteria    = [c for c in criterion_decisions if c.status == "yes"]
        not_met_criteria = [c for c in criterion_decisions if c.status == "no"]
        undet_criteria  = [c for c in criterion_decisions if c.status == "undetermined"]

        if met_criteria:
            lines.append(self._met_summary(met_criteria))
            supporting = [_truncate(c.criterion_text) for c in met_criteria[:_MAX_CRITERIA_IN_RATIONALE]]

        if not_met_criteria:
            lines.append(self._not_met_summary(not_met_criteria))
            denying = [_truncate(c.criterion_text) for c in not_met_criteria[:_MAX_CRITERIA_IN_RATIONALE]]

        if undet_criteria:
            lines.append(self._undetermined_summary(undet_criteria))

        # ------------------------------------------------------------------
        # 3. Evidence citations
        # ------------------------------------------------------------------
        evidence_lines = self._collect_evidence(criterion_decisions)
        if evidence_lines:
            lines.append(f"Supporting evidence: {'; '.join(evidence_lines[:3])}.")
            evidence = evidence_lines[:10]

        # ------------------------------------------------------------------
        # 4. Confidence interpretation
        # ------------------------------------------------------------------
        lines.append(self._confidence_line(confidence))

        # Confidence flags that affect review routing
        flag_lines = self._flag_lines(confidence)
        lines.extend(flag_lines)

        # ------------------------------------------------------------------
        # 5. Override rationale (replaces/augments normal lines)
        # ------------------------------------------------------------------
        if override_request:
            lines.extend(self._override_lines(override_request, verdict))

        return lines, supporting, denying, evidence

    # ------------------------------------------------------------------
    # Line builders
    # ------------------------------------------------------------------

    @staticmethod
    def _verdict_summary(
        verdict: DecisionVerdict,
        rule: RuleMatch,
        confidence: ConfidenceBreakdown,
    ) -> str:
        conf_label = _confidence_label(confidence.final_score)
        verdict_label = {
            DecisionVerdict.APPROVE:               "APPROVED",
            DecisionVerdict.DENY:                  "DENIED",
            DecisionVerdict.PEND_FOR_INFO:         "PENDED for additional information",
            DecisionVerdict.REFER_MEDICAL_DIRECTOR: "REFERRED to Medical Director",
        }[verdict]

        rule_label = {
            DecisionRuleType.ALL_PASS:           "all applicable criteria were met",
            DecisionRuleType.ANY_FAIL:           "one or more criteria were not met",
            DecisionRuleType.MISSING_INFO:       "required clinical information is missing",
            DecisionRuleType.LOW_CONFIDENCE:     "AI confidence was below threshold",
            DecisionRuleType.NO_CRITERIA:        "no criteria could be evaluated",
            DecisionRuleType.ALL_NOT_APPLICABLE: "all criteria are not applicable",
            DecisionRuleType.POLICY_CONFLICT:    "conflicting policy signals were detected",
            DecisionRuleType.OVERRIDE:           "reviewer override was applied",
        }.get(rule.rule_type, rule.rule_type.value)

        return (
            f"PA request {verdict_label} because {rule_label} "
            f"(confidence: {confidence.final_score:.0%} — {conf_label})."
        )

    @staticmethod
    def _met_summary(met: list[CriterionDecision]) -> str:
        count = len(met)
        if count == 1:
            return f"Met criterion: {_truncate(met[0].criterion_text, 120)}."
        samples = "; ".join(_truncate(c.criterion_text, 80) for c in met[:_MAX_CRITERIA_IN_RATIONALE])
        suffix = f" (and {count - _MAX_CRITERIA_IN_RATIONALE} more)" if count > _MAX_CRITERIA_IN_RATIONALE else ""
        return f"{count} criteria met: {samples}{suffix}."

    @staticmethod
    def _not_met_summary(not_met: list[CriterionDecision]) -> str:
        count = len(not_met)
        blocking = [c for c in not_met if c.is_blocking]
        if count == 1:
            c = not_met[0]
            blocking_tag = " [blocking]" if c.is_blocking else ""
            return f"Criterion NOT met{blocking_tag}: {_truncate(c.criterion_text, 120)}."
        samples = "; ".join(
            f"{_truncate(c.criterion_text, 70)}{' [blocking]' if c.is_blocking else ''}"
            for c in not_met[:_MAX_CRITERIA_IN_RATIONALE]
        )
        suffix = f" (and {count - _MAX_CRITERIA_IN_RATIONALE} more)" if count > _MAX_CRITERIA_IN_RATIONALE else ""
        blocking_note = f" ({len(blocking)} blocking)" if blocking else ""
        return f"{count} criteria NOT met{blocking_note}: {samples}{suffix}."

    @staticmethod
    def _undetermined_summary(undet: list[CriterionDecision]) -> str:
        count = len(undet)
        if count == 1:
            return (
                f"1 criterion could not be determined: "
                f"{_truncate(undet[0].criterion_text, 120)}. "
                "Additional clinical documentation required."
            )
        samples = "; ".join(_truncate(c.criterion_text, 70) for c in undet[:3])
        suffix = f" (and {count - 3} more)" if count > 3 else ""
        return (
            f"{count} criteria could not be determined: {samples}{suffix}. "
            "Additional clinical documentation required."
        )

    @staticmethod
    def _collect_evidence(criteria: list[CriterionDecision]) -> list[str]:
        seen: set[str] = set()
        refs: list[str] = []
        for c in criteria:
            for quote in c.evidence:
                key = quote[:60].lower()
                if key not in seen:
                    seen.add(key)
                    refs.append(f'"{_truncate(quote, 100)}"')
        return refs

    @staticmethod
    def _confidence_line(confidence: ConfidenceBreakdown) -> str:
        score = confidence.final_score
        parts = [
            f"criterion agreement {confidence.criterion_confidence_avg:.0%}",
            f"coverage {confidence.coverage_score:.0%}",
            f"evidence quality {confidence.evidence_quality_score:.0%}",
            f"extraction confidence {confidence.extraction_confidence:.0%}",
        ]
        if confidence.penalties > 0:
            parts.append(f"penalties −{confidence.penalties:.0%}")
        if confidence.bonuses > 0:
            parts.append(f"bonuses +{confidence.bonuses:.0%}")
        return (
            f"Confidence score {score:.0%}: "
            + ", ".join(parts) + "."
        )

    @staticmethod
    def _flag_lines(confidence: ConfidenceBreakdown) -> list[str]:
        lines = []
        if ConfidenceFlag.CROSS_POLICY_CONFLICT in confidence.flags:
            lines.append(
                "Note: evaluated policies produced conflicting signals — human review recommended."
            )
        if ConfidenceFlag.LOW_EXTRACTION_CONFIDENCE in confidence.flags:
            lines.append(
                f"Note: OCR/extraction confidence was {confidence.extraction_confidence:.0%} — "
                "clinical data may be incomplete or ambiguous."
            )
        if ConfidenceFlag.MISSING_EVIDENCE in confidence.flags:
            lines.append(
                "Note: multiple criteria lack supporting evidence quotes — "
                "grounding verification recommended."
            )
        return lines

    @staticmethod
    def _override_lines(override: OverrideRequest, final_verdict: DecisionVerdict) -> list[str]:
        lines = [
            f"Reviewer override applied by {override.reviewer_name or override.reviewer_id}: "
            f"decision changed to {final_verdict.value.upper()}."
        ]
        if override.override_reason:
            lines.append(f"Override reason: {override.override_reason}")
        if override.clinical_notes:
            lines.append(f"Clinical notes: {override.clinical_notes}")
        if override.regulatory_citation:
            lines.append(f"Regulatory citation: {override.regulatory_citation}")
        return lines
