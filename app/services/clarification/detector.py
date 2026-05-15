"""
Missing information detector for the clarification loop.

Analyses evaluation results from the reasoning engine to identify which
clinical information gaps are blocking a prior authorization decision.

Key responsibilities:
  - Scan EvaluationResult criterion_evaluations for UNDETERMINED criteria
  - Classify each gap into a MissingInfoCategory
  - Assign priority based on criterion type and position in policy
  - Mark items that were already asked in prior clarification attempts
  - Return a ranked MissingInfoAnalysis ready for question generation
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from app.services.clarification.models import (
    MissingInfoAnalysis,
    MissingInfoCategory,
    MissingInfoItem,
    QuestionPriority,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Keyword → category classification tables
# ---------------------------------------------------------------------------

_LAB_KEYWORDS = re.compile(
    r"\b(hba1c|a1c|hemoglobin a1c|glucose|hgb|lab|test|result|value|level|"
    r"fasting|lipid|cholesterol|ldl|hdl|creatinine|egfr|tsh|thyroid|"
    r"serum|plasma|urine|culture)\b",
    re.IGNORECASE,
)

_TREATMENT_KEYWORDS = re.compile(
    r"\b(treatment|therapy|drug|medication|tried|failed|prior|history|"
    r"inadequate|response|duration|course|adherence|compliance|"
    r"intolerant|contraindicated|alternative)\b",
    re.IGNORECASE,
)

_DIAGNOSIS_KEYWORDS = re.compile(
    r"\b(diagnos|condition|disorder|disease|syndrome|confirmed|icd|"
    r"documented|established|criteria|meet)\b",
    re.IGNORECASE,
)

_MEASUREMENT_KEYWORDS = re.compile(
    r"\b(bmi|body mass|weight|height|blood pressure|bp|systolic|diastolic|"
    r"pulse|heart rate|temperature|o2|oxygen|saturation|measurement)\b",
    re.IGNORECASE,
)

_ATTESTATION_KEYWORDS = re.compile(
    r"\b(attest|certify|certif|physician|provider|prescriber|specialist|"
    r"referral|order|authorize|supervise)\b",
    re.IGNORECASE,
)

_PRIOR_AUTH_KEYWORDS = re.compile(
    r"\b(prior auth|prior authorization|pa number|appeal|step therapy|"
    r"step edit|formulary|exception)\b",
    re.IGNORECASE,
)

_DURATION_KEYWORDS = re.compile(
    r"\b(duration|how long|weeks|months|years|days|period|course|"
    r"length|time on|since)\b",
    re.IGNORECASE,
)

_DATE_KEYWORDS = re.compile(
    r"\b(date|when|onset|start|begin|last visit|recent|current|"
    r"within \d+ (day|week|month|year))\b",
    re.IGNORECASE,
)

_PROCEDURE_KEYWORDS = re.compile(
    r"\b(procedure|surgery|intervention|indication|why|reason|"
    r"necessity|justif|appropriate|medically necessary)\b",
    re.IGNORECASE,
)

_CONTRAINDICATION_KEYWORDS = re.compile(
    r"\b(contraindic|allergy|allergic|adverse|reaction|intolerance|"
    r"cannot use|should not|avoid)\b",
    re.IGNORECASE,
)

_CATEGORY_PATTERNS: list[tuple[re.Pattern, MissingInfoCategory]] = [
    (_LAB_KEYWORDS,              MissingInfoCategory.LAB_RESULT),
    (_TREATMENT_KEYWORDS,        MissingInfoCategory.TREATMENT_HISTORY),
    (_DIAGNOSIS_KEYWORDS,        MissingInfoCategory.CLINICAL_DIAGNOSIS),
    (_MEASUREMENT_KEYWORDS,      MissingInfoCategory.CLINICAL_MEASUREMENT),
    (_ATTESTATION_KEYWORDS,      MissingInfoCategory.PROVIDER_ATTESTATION),
    (_PRIOR_AUTH_KEYWORDS,       MissingInfoCategory.PRIOR_AUTHORIZATION),
    (_DURATION_KEYWORDS,         MissingInfoCategory.DURATION),
    (_DATE_KEYWORDS,             MissingInfoCategory.DATES),
    (_PROCEDURE_KEYWORDS,        MissingInfoCategory.PROCEDURE_INDICATION),
    (_CONTRAINDICATION_KEYWORDS, MissingInfoCategory.CONTRAINDICATION_CHECK),
]


def _classify_category(text: str) -> MissingInfoCategory:
    for pattern, category in _CATEGORY_PATTERNS:
        if pattern.search(text):
            return category
    return MissingInfoCategory.OTHER


# ---------------------------------------------------------------------------
# Priority assignment
# ---------------------------------------------------------------------------

# Criterion types that typically block auto-adjudication
_CRITICAL_CRITERION_TYPES = frozenset({
    "medical_necessity",
    "clinical_indication",
    "safety",
    "contraindication",
    "eligibility",
})

_HIGH_CRITERION_TYPES = frozenset({
    "prior_treatment",
    "step_therapy",
    "lab_requirement",
    "diagnosis_requirement",
})


def _assign_priority(
    criterion_type: str | None,
    category: MissingInfoCategory,
    rationale: str,
) -> QuestionPriority:
    ctype = (criterion_type or "").lower()

    if ctype in _CRITICAL_CRITERION_TYPES:
        return QuestionPriority.CRITICAL
    if ctype in _HIGH_CRITERION_TYPES:
        return QuestionPriority.HIGH
    if category in (
        MissingInfoCategory.LAB_RESULT,
        MissingInfoCategory.CLINICAL_DIAGNOSIS,
        MissingInfoCategory.PROVIDER_ATTESTATION,
    ):
        return QuestionPriority.HIGH
    if category in (
        MissingInfoCategory.TREATMENT_HISTORY,
        MissingInfoCategory.CLINICAL_MEASUREMENT,
        MissingInfoCategory.PRIOR_AUTHORIZATION,
    ):
        return QuestionPriority.MEDIUM

    # Scan rationale for urgency signals
    if re.search(r"\b(required|must|critical|essential|cannot proceed)\b", rationale, re.I):
        return QuestionPriority.HIGH

    return QuestionPriority.MEDIUM


# ---------------------------------------------------------------------------
# Specific value extraction
# ---------------------------------------------------------------------------

def _extract_specific_value_needed(
    criterion_text: str,
    rationale: str,
    category: MissingInfoCategory,
) -> str:
    combined = f"{criterion_text} {rationale}"

    if category == MissingInfoCategory.LAB_RESULT:
        if re.search(r"hba1c|a1c|hemoglobin a1c", combined, re.I):
            return "HbA1c value (%) with collection date within the past 3 months"
        if re.search(r"glucose|fasting", combined, re.I):
            return "Fasting glucose value (mg/dL) with collection date"
        if re.search(r"egfr|creatinine", combined, re.I):
            return "eGFR or serum creatinine with collection date"
        return "Lab test name, result value, units, and collection date"

    if category == MissingInfoCategory.CLINICAL_MEASUREMENT:
        if re.search(r"bmi|body mass", combined, re.I):
            return "Current BMI (or height and weight with measurement date)"
        if re.search(r"blood pressure|bp", combined, re.I):
            return "Most recent blood pressure reading with measurement date"
        return "Current measurement value with date"

    if category == MissingInfoCategory.TREATMENT_HISTORY:
        return "Drug name, dose, duration of treatment, and reason for discontinuation (if applicable)"

    if category == MissingInfoCategory.DURATION:
        return "Start date and duration of current therapy"

    if category == MissingInfoCategory.DATES:
        return "Specific date(s) requested (onset, last visit, or procedure date)"

    return ""


# ---------------------------------------------------------------------------
# Main detector class
# ---------------------------------------------------------------------------

class MissingInfoDetector:
    """
    Analyses EvaluationResults to detect and classify clinical information gaps.
    """

    def detect(
        self,
        *,
        case_id: str,
        evaluation_results: dict[str, Any],   # dict[str, EvaluationResult]
        clarification_attempts: list[Any],     # list[ClarificationAttempt]
    ) -> MissingInfoAnalysis:
        """
        Build a MissingInfoAnalysis from workflow evaluation results.

        Parameters
        ----------
        case_id:
            Workflow case identifier.
        evaluation_results:
            The `evaluation_results` dict from PAWorkflowState — maps
            dedup_key → EvaluationResult.
        clarification_attempts:
            All prior ClarificationAttempt objects from workflow state.
        """
        prior_questions = [
            a.question for a in clarification_attempts if a.question
        ]
        asked_criterion_ids: set[str] = set()
        for attempt in clarification_attempts:
            asked_criterion_ids.update(attempt.missing_criteria or [])

        items: list[MissingInfoItem] = []
        total_undetermined = 0
        critical_count = 0

        for eval_result in evaluation_results.values():
            criteria_evals = getattr(eval_result, "criteria_evaluations", [])
            for ce in criteria_evals:
                met_value = getattr(ce.met, "value", str(ce.met))
                if met_value not in ("undetermined", "UNDETERMINED"):
                    continue

                total_undetermined += 1
                criterion_text = ce.criterion_text or ""
                criterion_type = getattr(ce, "criterion_type", None)
                notes = ce.notes or ""
                criterion_id = ce.criterion_id

                category = _classify_category(f"{criterion_text} {notes}")
                priority = _assign_priority(criterion_type, category, notes)
                specific_value = _extract_specific_value_needed(
                    criterion_text, notes, category
                )

                if priority == QuestionPriority.CRITICAL:
                    critical_count += 1

                item = MissingInfoItem(
                    category=category,
                    priority=priority,
                    description=self._describe_gap(criterion_text, notes, category),
                    affected_criteria=[criterion_id],
                    specific_value_needed=specific_value,
                    context=criterion_text[:300],
                    already_asked=(criterion_id in asked_criterion_ids),
                )
                items.append(item)

        logger.debug(
            "clarification.detector.done",
            case_id=case_id,
            total_undetermined=total_undetermined,
            critical_count=critical_count,
            already_asked=sum(1 for i in items if i.already_asked),
        )

        return MissingInfoAnalysis(
            case_id=case_id,
            items=items,
            total_undetermined=total_undetermined,
            critical_count=critical_count,
            has_prior_attempts=bool(clarification_attempts),
            prior_questions=prior_questions,
        )

    @staticmethod
    def _describe_gap(
        criterion_text: str,
        rationale: str,
        category: MissingInfoCategory,
    ) -> str:
        """Generate a short human-readable description of the information gap."""
        category_labels = {
            MissingInfoCategory.LAB_RESULT:             "Lab result required",
            MissingInfoCategory.TREATMENT_HISTORY:      "Treatment history documentation required",
            MissingInfoCategory.CLINICAL_DIAGNOSIS:     "Clinical diagnosis confirmation required",
            MissingInfoCategory.CLINICAL_MEASUREMENT:   "Clinical measurement required",
            MissingInfoCategory.PROVIDER_ATTESTATION:   "Provider attestation required",
            MissingInfoCategory.PRIOR_AUTHORIZATION:    "Prior authorization history required",
            MissingInfoCategory.INSURANCE_ELIGIBILITY:  "Insurance eligibility documentation required",
            MissingInfoCategory.PROCEDURE_INDICATION:   "Procedure indication documentation required",
            MissingInfoCategory.CONTRAINDICATION_CHECK: "Contraindication assessment required",
            MissingInfoCategory.DURATION:               "Duration of therapy documentation required",
            MissingInfoCategory.DATES:                  "Date documentation required",
            MissingInfoCategory.OTHER:                  "Additional clinical documentation required",
        }
        label = category_labels.get(category, "Documentation required")
        # Append the first sentence of the criterion for context
        first_sentence = re.split(r"[.;]", criterion_text)[0][:120].strip()
        if first_sentence:
            return f"{label}: {first_sentence}"
        return label
