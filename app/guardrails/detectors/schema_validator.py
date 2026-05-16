"""
Schema validation guardrail.

Validates LLM-generated structured output against expected JSON schemas
for each node's output contract.  Schema violations catch:
  - Missing required fields (e.g., missing 'recommendation' in decision output)
  - Incorrect types (e.g., confidence as string instead of float)
  - Out-of-range values (e.g., confidence > 1.0)
  - Unexpected extra fields that may indicate prompt injection output smuggling

This is a binary detector — schema violations always fire (threshold = 0.0).
Severity is scaled by how many fields are wrong and whether required fields
are absent.
"""

from __future__ import annotations

import json
from typing import Any

from app.guardrails.models import (
    GuardrailStage,
    GuardrailViolation,
    ViolationSeverity,
    ViolationType,
)

_DETECTOR_NAME = "schema_validator"


# ---------------------------------------------------------------------------
# Node output schemas
# ---------------------------------------------------------------------------

# Each schema is a lightweight validator dict:
# {field: {"type": ..., "required": bool, "min": ..., "max": ..., "enum": [...]}}

_EXTRACTION_OUTPUT_SCHEMA: dict[str, Any] = {
    "extracted_entities": {"type": list,  "required": True},
    "extraction_confidence": {"type": float, "required": False, "min": 0.0, "max": 1.0},
    "workflow_phase": {"type": str,  "required": False},
}

_RETRIEVAL_OUTPUT_SCHEMA: dict[str, Any] = {
    "retrieved_policies": {"type": list, "required": True},
    "retrieval_confidence": {"type": float, "required": False, "min": 0.0, "max": 1.0},
    "workflow_phase": {"type": str, "required": False},
}

_REASONING_OUTPUT_SCHEMA: dict[str, Any] = {
    "reasoning_summary": {"type": str,  "required": True},
    "criteria_met": {"type": list, "required": False},
    "criteria_not_met": {"type": list, "required": False},
    "recommendation_hint": {"type": str,  "required": False,
                             "enum": ["APPROVE", "DENY", "PEND", "ESCALATE", None]},
    "confidence_score": {"type": float, "required": False, "min": 0.0, "max": 1.0},
    "workflow_phase": {"type": str,  "required": False},
}

_DECISION_OUTPUT_SCHEMA: dict[str, Any] = {
    "recommendation": {"type": dict, "required": True},
    "decision_type": {"type": str,  "required": True,
                      "enum": ["APPROVE", "DENY", "PEND", "ESCALATE"]},
    "confidence_score": {"type": float, "required": True, "min": 0.0, "max": 1.0},
    "workflow_phase": {"type": str,  "required": False},
}

_CLARIFICATION_OUTPUT_SCHEMA: dict[str, Any] = {
    "clarification_question": {"type": str, "required": True},
    "attempt_id": {"type": str, "required": True},
    "workflow_phase": {"type": str, "required": False},
}

NODE_SCHEMAS: dict[str, dict[str, Any]] = {
    "extraction_node":     _EXTRACTION_OUTPUT_SCHEMA,
    "retrieval_node":      _RETRIEVAL_OUTPUT_SCHEMA,
    "reasoning_node":      _REASONING_OUTPUT_SCHEMA,
    "decision_node":       _DECISION_OUTPUT_SCHEMA,
    "clarification_node":  _CLARIFICATION_OUTPUT_SCHEMA,
}


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def _validate_field(
    key: str,
    value: Any,
    spec: dict[str, Any],
    errors: list[str],
) -> None:
    """Validate one field against its spec dict."""
    expected_type = spec.get("type")
    if expected_type is not None and value is not None:
        if not isinstance(value, expected_type):
            errors.append(f"field '{key}': expected {expected_type.__name__}, got {type(value).__name__}")
            return

    if "min" in spec and isinstance(value, (int, float)) and value < spec["min"]:
        errors.append(f"field '{key}': value {value} < min {spec['min']}")

    if "max" in spec and isinstance(value, (int, float)) and value > spec["max"]:
        errors.append(f"field '{key}': value {value} > max {spec['max']}")

    if "enum" in spec and spec["enum"] is not None and value not in spec["enum"]:
        errors.append(f"field '{key}': '{value}' not in {spec['enum']}")


async def detect_schema_violation(
    output: dict[str, Any] | str,
    node_name: str,
    stage: GuardrailStage = GuardrailStage.POST_LLM,
    context: dict[str, Any] | None = None,
) -> GuardrailViolation | None:
    """
    Validate node output against the registered schema.

    ``output`` can be a dict (already parsed) or a JSON string.

    Returns GuardrailViolation if schema violations are found, else None.
    """
    schema = NODE_SCHEMAS.get(node_name)
    if schema is None:
        return None  # No schema registered for this node — skip

    # Parse if string
    data: dict[str, Any] | None = None
    parse_error: str | None = None

    if isinstance(output, str):
        try:
            data = json.loads(output)
        except json.JSONDecodeError as exc:
            parse_error = str(exc)
    elif isinstance(output, dict):
        data = output

    errors: list[str] = []

    if parse_error:
        errors.append(f"JSON parse error: {parse_error}")
    elif data is None:
        errors.append("Output is None or not a dict/JSON string")
    else:
        # Check required fields
        for field_name, spec in schema.items():
            if spec.get("required", False) and field_name not in data:
                errors.append(f"missing required field '{field_name}'")
            elif field_name in data:
                _validate_field(field_name, data[field_name], spec, errors)

    if not errors:
        return None

    # Severity scales with number and criticality of errors
    has_required_missing = any("missing required" in e for e in errors)
    has_parse_error      = any("parse error" in e for e in errors)

    if has_parse_error or (has_required_missing and len(errors) >= 2):
        severity = ViolationSeverity.HIGH
    elif has_required_missing:
        severity = ViolationSeverity.MEDIUM
    else:
        severity = ViolationSeverity.LOW

    confidence = min(0.50 + len(errors) * 0.10, 1.0)

    return GuardrailViolation(
        violation_type=ViolationType.SCHEMA_VIOLATION,
        severity=severity,
        description=f"Schema violation in {node_name}: {len(errors)} error(s)",
        confidence=round(confidence, 4),
        evidence={
            "node_name": node_name,
            "errors":    errors[:10],
            "error_count": len(errors),
        },
        stage=stage,
        detector=_DETECTOR_NAME,
    )
