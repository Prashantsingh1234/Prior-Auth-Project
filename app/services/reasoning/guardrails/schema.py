"""
JSON schema validator for LLM output.

Validates that the LLM response:
  1. Is valid JSON
  2. Matches the expected output schema (required fields, types, enum values)
  3. Contains at least one criterion evaluation
  4. Has confidence values in [0, 1]
  5. Has non-empty rationale strings
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from app.services.reasoning.guardrails.base import BaseGuardrail, GuardrailContext
from app.services.reasoning.models import (
    GuardrailResult,
    GuardrailViolation,
    ViolationSeverity,
    ViolationType,
)
from app.services.reasoning.prompts import CRITERION_EVAL_SCHEMA

logger = structlog.get_logger(__name__)

VALID_STATUSES = {"MET", "NOT_MET", "UNDETERMINED"}


class SchemaValidator(BaseGuardrail):
    """
    Validates the structural integrity of the LLM JSON output.

    Schema failures are HIGH severity — the output cannot be used at all.
    Field-level issues are MEDIUM severity — individual criteria may be salvageable.
    """

    name = "schema_validator"

    async def check(self, ctx: GuardrailContext) -> GuardrailResult:
        violations: list[GuardrailViolation] = []

        # 1. Raw output must be parseable JSON
        raw = ctx.raw_output or ""
        parsed: dict[str, Any] | None = None
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            violations.append(GuardrailViolation(
                violation_type=ViolationType.SCHEMA_INVALID,
                severity=ViolationSeverity.HIGH,
                message=f"LLM output is not valid JSON: {exc}",
                details={"raw_preview": raw[:200]},
            ))
            return self._fail(violations)

        if not isinstance(parsed, dict):
            violations.append(GuardrailViolation(
                violation_type=ViolationType.SCHEMA_INVALID,
                severity=ViolationSeverity.HIGH,
                message="LLM output is JSON but not an object (dict)",
            ))
            return self._fail(violations)

        # 2. Required top-level fields
        for required in ("criterion_evaluations", "overall_confidence", "overall_rationale"):
            if required not in parsed:
                violations.append(GuardrailViolation(
                    violation_type=ViolationType.SCHEMA_INVALID,
                    severity=ViolationSeverity.HIGH,
                    message=f"Missing required field: {required}",
                    details={"available_keys": list(parsed.keys())},
                ))

        if violations:
            return self._fail(violations)

        # 3. criterion_evaluations must be a non-empty list
        evals = parsed.get("criterion_evaluations", [])
        if not isinstance(evals, list) or len(evals) == 0:
            violations.append(GuardrailViolation(
                violation_type=ViolationType.SCHEMA_INVALID,
                severity=ViolationSeverity.HIGH,
                message="criterion_evaluations must be a non-empty array",
            ))
            return self._fail(violations)

        # 4. Per-criterion validation
        for i, ev in enumerate(evals):
            if not isinstance(ev, dict):
                violations.append(GuardrailViolation(
                    violation_type=ViolationType.SCHEMA_INVALID,
                    severity=ViolationSeverity.HIGH,
                    message=f"criterion_evaluations[{i}] is not an object",
                    criterion_id=str(i),
                ))
                continue

            cid = ev.get("criterion_id", f"idx_{i}")

            # Required per-criterion fields
            for field in ("criterion_id", "status", "confidence", "rationale"):
                if field not in ev:
                    violations.append(GuardrailViolation(
                        violation_type=ViolationType.SCHEMA_INVALID,
                        severity=ViolationSeverity.MEDIUM,
                        message=f"Criterion {cid} missing required field: {field}",
                        criterion_id=cid,
                    ))

            # Status must be valid enum value
            status = ev.get("status", "")
            if status not in VALID_STATUSES:
                violations.append(GuardrailViolation(
                    violation_type=ViolationType.SCHEMA_INVALID,
                    severity=ViolationSeverity.HIGH,
                    message=f"Criterion {cid} has invalid status '{status}'; must be one of {VALID_STATUSES}",
                    criterion_id=cid,
                ))

            # Confidence must be 0-1 float
            conf = ev.get("confidence")
            if not isinstance(conf, (int, float)) or not (0.0 <= float(conf) <= 1.0):
                violations.append(GuardrailViolation(
                    violation_type=ViolationType.SCHEMA_INVALID,
                    severity=ViolationSeverity.MEDIUM,
                    message=f"Criterion {cid} confidence {conf!r} is not in [0.0, 1.0]",
                    criterion_id=cid,
                    details={"confidence": conf},
                ))

            # Rationale must be a non-empty string
            rationale = ev.get("rationale", "")
            if not isinstance(rationale, str) or len(rationale.strip()) < 10:
                violations.append(GuardrailViolation(
                    violation_type=ViolationType.SCHEMA_INVALID,
                    severity=ViolationSeverity.MEDIUM,
                    message=f"Criterion {cid} rationale is empty or too short",
                    criterion_id=cid,
                ))

            # Evidence citations validation
            citations = ev.get("evidence_citations", [])
            if isinstance(citations, list):
                for j, cit in enumerate(citations):
                    if not isinstance(cit, dict):
                        continue
                    for req_field in ("document_id", "quote", "relevance_explanation"):
                        if req_field not in cit or not cit.get(req_field):
                            violations.append(GuardrailViolation(
                                violation_type=ViolationType.SCHEMA_INVALID,
                                severity=ViolationSeverity.MEDIUM,
                                message=f"Citation {j} in criterion {cid} missing: {req_field}",
                                criterion_id=cid,
                            ))

        # 5. Overall confidence validation
        oc = parsed.get("overall_confidence")
        if not isinstance(oc, (int, float)) or not (0.0 <= float(oc) <= 1.0):
            violations.append(GuardrailViolation(
                violation_type=ViolationType.SCHEMA_INVALID,
                severity=ViolationSeverity.MEDIUM,
                message=f"overall_confidence {oc!r} is not in [0.0, 1.0]",
            ))

        if violations:
            logger.warning(
                "guardrail.schema_violations",
                case_id=ctx.case_id,
                count=len(violations),
                high_count=sum(1 for v in violations if v.severity == ViolationSeverity.HIGH),
            )

        passed = not any(v.severity in (ViolationSeverity.HIGH, ViolationSeverity.CRITICAL)
                         for v in violations)
        result = GuardrailResult(
            passed=passed,
            violations=violations,
            corrected_output=parsed if passed else None,
        )
        return result
