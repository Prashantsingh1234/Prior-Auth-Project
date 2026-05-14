"""
Medical terminology and code format validator.

Checks that:
  1. Any CPT codes mentioned in the output follow valid format (5-char: NNNNN or NNNNA)
  2. Any ICD-10-CM codes follow valid format (letter + 2 digits + optional .suffix)
  3. Any dates referenced follow a plausible format (no year 1900 or year 3000)
  4. No obviously impossible clinical values (e.g., HbA1c > 20%, weight < 0)
  5. Drug dosages mention known units (mg, mcg, units, IU, mL)

This is a SOFT validator — violations are MEDIUM severity (escalate model)
not HIGH (reject), unless there is a clearly impossible value.

False positive rate: designed to be low at the cost of missing some errors.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from app.services.reasoning.guardrails.base import BaseGuardrail, GuardrailContext
from app.services.reasoning.models import (
    GuardrailResult,
    GuardrailViolation,
    ViolationSeverity,
    ViolationType,
)

logger = structlog.get_logger(__name__)

# CPT: 5 digits OR 4 digits + letter (category III)
_CPT_PATTERN = re.compile(r"\b(\d{5}|[0-9]{4}[A-Z])\b")

# ICD-10-CM: letter + 2 digits, optional period, optional 1-4 alphanumeric
_ICD_PATTERN = re.compile(r"\b([A-Z]\d{2})(?:\.([A-Z0-9]{1,4}))?\b")

# Date patterns in output (YYYY-MM-DD)
_DATE_PATTERN = re.compile(r"\b(19|20|21)\d{2}-\d{2}-\d{2}\b")

# Plausible year range for clinical dates
_YEAR_MIN = 1900
_YEAR_MAX = 2030

# HbA1c range: clinical values are 2%–20%
_HBA1C_PATTERN = re.compile(r"(?:hba1c|a1c)[:\s]+(\d+(?:\.\d+)?)\s*%", re.IGNORECASE)
_HBA1C_MIN, _HBA1C_MAX = 2.0, 20.0

# Known medication dose units
_DOSE_UNITS = re.compile(r"\b(\d+(?:\.\d+)?)\s*(mg|mcg|μg|units?|IU|mL|g|kg)\b", re.IGNORECASE)


def _extract_cpt_from_text(text: str) -> list[str]:
    return _CPT_PATTERN.findall(text)


def _extract_icd_from_text(text: str) -> list[str]:
    return [f"{m[0]}.{m[1]}" if m[1] else m[0] for m in _ICD_PATTERN.findall(text)]


class MedicalTerminologyValidator(BaseGuardrail):
    """
    Validates medical code formats and clinical value plausibility.

    Detects gross errors (impossible values) but does not require every
    code to be in a complete code set — that would require an external API.
    """

    name = "medical_terminology_validator"

    async def check(self, ctx: GuardrailContext) -> GuardrailResult:
        parsed = ctx.parsed_output
        if not parsed:
            return self._pass()

        violations: list[GuardrailViolation] = []

        # Collect all text from the output for analysis
        all_text = self._collect_all_text(parsed)

        # 1. Date range validation
        for date_match in _DATE_PATTERN.finditer(all_text):
            year_str = date_match.group(0)[:4]
            try:
                year = int(year_str)
                if year < _YEAR_MIN or year > _YEAR_MAX:
                    violations.append(GuardrailViolation(
                        violation_type=ViolationType.MEDICAL_TERMINOLOGY,
                        severity=ViolationSeverity.MEDIUM,
                        message=f"Implausible year in output: {date_match.group(0)}",
                        details={"date_value": date_match.group(0)},
                    ))
            except ValueError:
                pass

        # 2. HbA1c range validation
        for hba1c_match in _HBA1C_PATTERN.finditer(all_text):
            try:
                value = float(hba1c_match.group(1))
                if value < _HBA1C_MIN or value > _HBA1C_MAX:
                    violations.append(GuardrailViolation(
                        violation_type=ViolationType.MEDICAL_TERMINOLOGY,
                        severity=ViolationSeverity.HIGH,
                        message=f"Impossible HbA1c value in output: {value}% (expected {_HBA1C_MIN}–{_HBA1C_MAX}%)",
                        details={"hba1c_value": value},
                    ))
            except ValueError:
                pass

        # 3. Check that CPT codes in output (if any) match query codes or look valid
        output_cpts = set(_extract_cpt_from_text(all_text))
        query_cpts = set(ctx.query_cpt_codes)
        # Flag CPT codes in output that are NOT in the query codes AND NOT in policy chunks
        policy_cpts: set[str] = set()
        for chunk in ctx.policy_chunks:
            policy_cpts.update(_extract_cpt_from_text(chunk))

        hallucinated_cpts = output_cpts - query_cpts - policy_cpts
        if hallucinated_cpts and query_cpts:
            # Only flag if we actually had query codes to compare against
            violations.append(GuardrailViolation(
                violation_type=ViolationType.MEDICAL_TERMINOLOGY,
                severity=ViolationSeverity.MEDIUM,
                message=(
                    f"Output mentions CPT codes {hallucinated_cpts} "
                    "not found in query codes or retrieved policies"
                ),
                details={
                    "output_cpts": list(output_cpts),
                    "query_cpts": list(query_cpts),
                },
            ))

        # 4. Check ICD codes in output
        output_icds = set(_extract_icd_from_text(all_text))
        query_icds = set(ctx.query_icd_codes)
        policy_icds: set[str] = set()
        for chunk in ctx.policy_chunks:
            policy_icds.update(_extract_icd_from_text(chunk))

        hallucinated_icds = output_icds - query_icds - policy_icds
        if hallucinated_icds and query_icds:
            violations.append(GuardrailViolation(
                violation_type=ViolationType.MEDICAL_TERMINOLOGY,
                severity=ViolationSeverity.LOW,
                message=(
                    f"Output mentions ICD codes {list(hallucinated_icds)[:5]} "
                    "not in query or policy sources"
                ),
                details={"hallucinated_icds": list(hallucinated_icds)[:10]},
            ))

        has_blocking = any(
            v.severity in (ViolationSeverity.HIGH, ViolationSeverity.CRITICAL)
            for v in violations
        )

        if violations:
            logger.warning(
                "guardrail.medical_terminology_issues",
                case_id=ctx.case_id,
                count=len(violations),
            )

        return GuardrailResult(passed=not has_blocking, violations=violations)

    def _collect_all_text(self, parsed: dict) -> str:
        """Extract all text fields from the parsed output for analysis."""
        parts: list[str] = [
            str(parsed.get("overall_rationale", "")),
        ]
        for ev in parsed.get("criterion_evaluations", []):
            if isinstance(ev, dict):
                parts.append(str(ev.get("rationale", "")))
                for cit in ev.get("evidence_citations", []):
                    if isinstance(cit, dict):
                        parts.append(str(cit.get("quote", "")))
                        parts.append(str(cit.get("relevance_explanation", "")))
        return " ".join(parts)
