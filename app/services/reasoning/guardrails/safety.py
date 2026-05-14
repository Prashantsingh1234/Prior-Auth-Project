"""
Safety and PII checker for LLM reasoning outputs.

Detects:
  1. PII leakage — SSN, full DOB, credit card patterns in output text
  2. Unsafe recommendations — absolute denial language without basis
  3. Harmful clinical statements — fabricated prognoses, treatment mandates
  4. Truncated output — output appears cut off mid-sentence
  5. Prompt injection echoing — output echoes back the prompt instructions

PII is CRITICAL severity — block output immediately.
Other safety issues are HIGH severity — reject and retry.
"""

from __future__ import annotations

import re

import structlog

from app.services.reasoning.guardrails.base import BaseGuardrail, GuardrailContext
from app.services.reasoning.models import (
    GuardrailResult,
    GuardrailViolation,
    ViolationSeverity,
    ViolationType,
)

logger = structlog.get_logger(__name__)

# PII patterns
_SSN_PATTERN     = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CCN_PATTERN     = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
_FULL_DOB_PATTERN = re.compile(
    r"\b(?:born|dob|date of birth)[:\s]+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    re.IGNORECASE,
)

# Unsafe recommendation patterns (absolute statements without evidence)
_UNSAFE_DENIAL_PATTERNS = [
    re.compile(r"\bpatient does not qualify for any coverage\b", re.IGNORECASE),
    re.compile(r"\bshould never receive\b", re.IGNORECASE),
    re.compile(r"\bmedically contraindicated for life\b", re.IGNORECASE),
]

# Harmful prognosis patterns
_PROGNOSIS_PATTERNS = [
    re.compile(r"\bwill die without (this )?treatment\b", re.IGNORECASE),
    re.compile(r"\bimminent risk of death\b", re.IGNORECASE),
]

# Truncation indicators (output ends mid-sentence or with "...")
_TRUNCATION_PATTERN = re.compile(r"(\.{3,}|…|\.\.\.)$")

# Prompt injection: echoing back instruction phrases
_INJECTION_PHRASES = [
    "return only valid json",
    "prohibited:",
    "citation requirements:",
    "status definitions:",
]

# Minimum output length to check truncation (very short outputs are checked differently)
MIN_OUTPUT_LENGTH_FOR_TRUNCATION = 200


class SafetyChecker(BaseGuardrail):
    """
    Detects PII, unsafe outputs, and prompt injection in LLM responses.
    """

    name = "safety_checker"

    async def check(self, ctx: GuardrailContext) -> GuardrailResult:
        raw = ctx.raw_output or ""
        parsed = ctx.parsed_output or {}
        violations: list[GuardrailViolation] = []

        # 1. PII detection in raw output
        if _SSN_PATTERN.search(raw):
            violations.append(GuardrailViolation(
                violation_type=ViolationType.UNSAFE_CONTENT,
                severity=ViolationSeverity.CRITICAL,
                message="Potential SSN detected in LLM output — blocking output",
            ))

        if _CCN_PATTERN.search(raw):
            violations.append(GuardrailViolation(
                violation_type=ViolationType.UNSAFE_CONTENT,
                severity=ViolationSeverity.CRITICAL,
                message="Potential credit card number detected in LLM output",
            ))

        if _FULL_DOB_PATTERN.search(raw):
            violations.append(GuardrailViolation(
                violation_type=ViolationType.UNSAFE_CONTENT,
                severity=ViolationSeverity.HIGH,
                message="Full date of birth pattern detected in LLM output",
            ))

        # 2. Unsafe denial recommendations
        for pattern in _UNSAFE_DENIAL_PATTERNS:
            if pattern.search(raw):
                violations.append(GuardrailViolation(
                    violation_type=ViolationType.UNSAFE_CONTENT,
                    severity=ViolationSeverity.HIGH,
                    message=f"Unsafe absolute denial statement detected: '{pattern.pattern}'",
                ))

        # 3. Harmful prognosis patterns
        for pattern in _PROGNOSIS_PATTERNS:
            if pattern.search(raw):
                violations.append(GuardrailViolation(
                    violation_type=ViolationType.UNSAFE_CONTENT,
                    severity=ViolationSeverity.HIGH,
                    message=f"Harmful prognosis statement detected: '{pattern.pattern}'",
                ))

        # 4. Truncation detection
        if len(raw) >= MIN_OUTPUT_LENGTH_FOR_TRUNCATION:
            # Strip trailing whitespace from the raw JSON string
            raw_stripped = raw.strip().rstrip("}")
            if _TRUNCATION_PATTERN.search(raw_stripped):
                violations.append(GuardrailViolation(
                    violation_type=ViolationType.TRUNCATED_OUTPUT,
                    severity=ViolationSeverity.HIGH,
                    message="LLM output appears truncated (ends with '...')",
                ))

            # Check if JSON appears incomplete (unbalanced braces)
            open_braces = raw.count("{")
            close_braces = raw.count("}")
            if open_braces > close_braces + 2:
                violations.append(GuardrailViolation(
                    violation_type=ViolationType.TRUNCATED_OUTPUT,
                    severity=ViolationSeverity.HIGH,
                    message=(
                        f"JSON output has unbalanced braces ({open_braces} open, "
                        f"{close_braces} close) — likely truncated"
                    ),
                ))

        # 5. Prompt injection / instruction echoing
        raw_lower = raw.lower()
        for phrase in _INJECTION_PHRASES:
            if phrase in raw_lower:
                violations.append(GuardrailViolation(
                    violation_type=ViolationType.UNSAFE_CONTENT,
                    severity=ViolationSeverity.MEDIUM,
                    message=f"LLM output echoes system prompt instruction: '{phrase}'",
                ))
                break  # One violation is enough

        if violations:
            critical = [v for v in violations if v.severity == ViolationSeverity.CRITICAL]
            high = [v for v in violations if v.severity == ViolationSeverity.HIGH]
            logger.warning(
                "guardrail.safety_violations",
                case_id=ctx.case_id,
                critical_count=len(critical),
                high_count=len(high),
            )

        has_blocking = any(
            v.severity in (ViolationSeverity.HIGH, ViolationSeverity.CRITICAL)
            for v in violations
        )
        return GuardrailResult(passed=not has_blocking, violations=violations)
