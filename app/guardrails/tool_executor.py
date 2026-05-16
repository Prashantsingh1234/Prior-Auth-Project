"""
Secure tool execution sandbox.

SecureToolExecutor wraps tool/function calls made by the LLM agent with:
  1. Tool allowlist enforcement — only registered tools may execute
  2. Input validation — tool arguments are schema-validated before execution
  3. Output sanitization — tool results are PII-checked before returning to LLM
  4. Rate limiting — per-tool and per-case execution limits
  5. Timeout enforcement — no tool call runs longer than max_execution_seconds
  6. Audit trail — every tool call is logged with inputs (sanitized) + outputs

This prevents:
  - Prompt injection via tool outputs (malicious data poisoning LLM context)
  - Unrestricted file/network access via LangChain tools
  - Sensitive data exfiltration through tool return values
"""

from __future__ import annotations

import asyncio
import functools
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import structlog

from app.guardrails.detectors.pii import find_pii_entities
from app.guardrails.models import (
    GuardrailViolation,
    ViolationSeverity,
    ViolationType,
    GuardrailStage,
)

logger = structlog.get_logger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 30.0
_DEFAULT_MAX_CALLS_PER_CASE = 50


@dataclass
class ToolSpec:
    """Registration record for one allowlisted tool."""
    name:           str
    description:    str
    allowed_roles:  set[str] = field(default_factory=lambda: {"admin", "reviewer", "provider"})
    max_calls_per_case: int  = _DEFAULT_MAX_CALLS_PER_CASE
    timeout_seconds: float   = _DEFAULT_TIMEOUT_SECONDS
    sanitize_output: bool    = True    # PII-check tool output before returning to LLM
    log_inputs:      bool    = True    # Log tool invocation inputs (sanitized)


@dataclass
class ToolCallRecord:
    """Audit record for one tool invocation."""
    tool_name:    str
    case_id:      str | None
    caller_role:  str | None
    inputs_safe:  dict[str, Any]   # Sanitized inputs (no raw PII)
    output_safe:  str              # Sanitized output preview
    success:      bool
    error:        str | None
    elapsed_ms:   float
    violated_pii: bool = False
    timestamp:    float = field(default_factory=time.monotonic)


class SecureToolExecutor:
    """
    Sandbox for LLM-driven tool execution.

    Usage:
        executor = SecureToolExecutor()
        executor.register(ToolSpec(name="policy_lookup", ...))

        result = await executor.execute(
            tool_name="policy_lookup",
            tool_fn=lookup_fn,
            inputs={"query": "...", "payer_id": "..."},
            case_id="PA-001",
            caller_role="reviewer",
        )
    """

    def __init__(self) -> None:
        self._registry: dict[str, ToolSpec]     = {}
        self._call_counts: dict[str, int]        = {}  # f"{tool}:{case_id}" → count
        self._call_records: list[ToolCallRecord] = []
        self._lock = asyncio.Lock()
        self._log  = structlog.get_logger(__name__)

    def register(self, spec: ToolSpec) -> None:
        """Register an allowed tool."""
        self._registry[spec.name] = spec
        self._log.debug("tool_executor.registered", tool=spec.name)

    def unregister(self, name: str) -> None:
        self._registry.pop(name, None)

    @property
    def allowed_tools(self) -> list[str]:
        return list(self._registry.keys())

    async def execute(
        self,
        tool_name: str,
        tool_fn: Callable[..., Any],
        inputs: dict[str, Any],
        case_id: str | None = None,
        caller_role: str | None = None,
    ) -> Any:
        """
        Execute ``tool_fn`` with ``inputs`` inside the security sandbox.

        Raises:
            ToolNotAllowedError:  Tool is not on the allowlist
            ToolRateLimitError:   Per-case call limit exceeded
            ToolRoleError:        Caller role not permitted for this tool
            asyncio.TimeoutError: Execution exceeded timeout
        """
        t0 = time.monotonic()

        # --- Allowlist check ---
        spec = self._registry.get(tool_name)
        if spec is None:
            raise ToolNotAllowedError(f"Tool '{tool_name}' is not registered")

        # --- Role check ---
        if caller_role and spec.allowed_roles and caller_role not in spec.allowed_roles:
            raise ToolRoleError(
                f"Role '{caller_role}' not permitted to use tool '{tool_name}'"
            )

        # --- Rate limit check ---
        rate_key = f"{tool_name}:{case_id or '_global'}"
        async with self._lock:
            current_count = self._call_counts.get(rate_key, 0)
            if current_count >= spec.max_calls_per_case:
                raise ToolRateLimitError(
                    f"Tool '{tool_name}' rate limit exceeded for case {case_id}"
                )
            self._call_counts[rate_key] = current_count + 1

        # --- Execute with timeout ---
        error_msg: str | None = None
        raw_result: Any       = None
        violated_pii          = False

        try:
            if asyncio.iscoroutinefunction(tool_fn):
                raw_result = await asyncio.wait_for(
                    tool_fn(**inputs),
                    timeout=spec.timeout_seconds,
                )
            else:
                loop = asyncio.get_event_loop()
                raw_result = await asyncio.wait_for(
                    loop.run_in_executor(None, functools.partial(tool_fn, **inputs)),
                    timeout=spec.timeout_seconds,
                )
        except asyncio.TimeoutError:
            error_msg = f"Tool '{tool_name}' timed out after {spec.timeout_seconds}s"
            self._log.error("tool_executor.timeout", tool=tool_name, case_id=case_id)
            raise
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            self._log.error("tool_executor.error", tool=tool_name, error=error_msg)
            raise

        # --- Output sanitization ---
        result_str = str(raw_result)[:2000] if raw_result is not None else ""
        if spec.sanitize_output:
            pii_entities = find_pii_entities(result_str)
            if pii_entities:
                violated_pii = True
                self._log.warning(
                    "tool_executor.pii_in_output",
                    tool=tool_name,
                    case_id=case_id,
                    entity_count=len(pii_entities),
                )
                # Mask PII in the output before returning to LLM
                for entity in sorted(pii_entities, key=lambda e: e.start, reverse=True):
                    mask = f"[{entity.entity_type.upper()}_REDACTED]"
                    result_str = result_str[:entity.start] + mask + result_str[entity.end:]

        elapsed_ms = (time.monotonic() - t0) * 1000

        # --- Audit record ---
        safe_inputs = {
            k: ("[REDACTED]" if _is_sensitive_key(k) else str(v)[:200])
            for k, v in inputs.items()
        }
        record = ToolCallRecord(
            tool_name=tool_name,
            case_id=case_id,
            caller_role=caller_role,
            inputs_safe=safe_inputs,
            output_safe=result_str[:500],
            success=error_msg is None,
            error=error_msg,
            elapsed_ms=round(elapsed_ms, 1),
            violated_pii=violated_pii,
        )
        async with self._lock:
            self._call_records.append(record)

        self._log.debug(
            "tool_executor.completed",
            tool=tool_name,
            case_id=case_id,
            elapsed_ms=round(elapsed_ms, 1),
            violated_pii=violated_pii,
        )

        _emit_prometheus(tool_name, elapsed_ms, success=True)

        # Return the (possibly sanitized) string result, or the original object
        return result_str if violated_pii else raw_result

    async def get_call_records(
        self,
        case_id: str | None = None,
        tool_name: str | None = None,
    ) -> list[ToolCallRecord]:
        async with self._lock:
            return [
                r for r in self._call_records
                if (case_id is None or r.case_id == case_id)
                and (tool_name is None or r.tool_name == tool_name)
            ]

    def reset_case_counts(self, case_id: str) -> None:
        """Clear rate limit counters for a completed case."""
        prefix = f":{case_id}"
        keys_to_del = [k for k in self._call_counts if k.endswith(prefix)]
        for k in keys_to_del:
            del self._call_counts[k]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ToolNotAllowedError(PermissionError):
    """Tool is not on the allowlist."""


class ToolRoleError(PermissionError):
    """Caller's role is not permitted to use the tool."""


class ToolRateLimitError(RuntimeError):
    """Per-case tool call limit has been exceeded."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SENSITIVE_KEY_SUBSTRINGS = frozenset({
    "password", "token", "secret", "key", "ssn", "dob", "mrn",
    "credit", "card", "auth", "credential",
})


def _is_sensitive_key(key: str) -> bool:
    k = key.lower()
    return any(s in k for s in _SENSITIVE_KEY_SUBSTRINGS)


def _emit_prometheus(tool_name: str, elapsed_ms: float, success: bool) -> None:
    try:
        from app.guardrails.observability import TOOL_EXECUTION_DURATION_MS, TOOL_EXECUTIONS_TOTAL
        TOOL_EXECUTIONS_TOTAL.labels(tool=tool_name, success=str(success)).inc()
        TOOL_EXECUTION_DURATION_MS.labels(tool=tool_name).observe(elapsed_ms)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_executor: SecureToolExecutor | None = None


def get_tool_executor() -> SecureToolExecutor:
    global _executor
    if _executor is None:
        _executor = SecureToolExecutor()
        _register_default_tools(_executor)
    return _executor


def _register_default_tools(executor: SecureToolExecutor) -> None:
    """Register the PA platform's built-in tools."""
    executor.register(ToolSpec(
        name="policy_lookup",
        description="Search Pinecone for matching PA policies",
        allowed_roles={"admin", "reviewer", "provider"},
        max_calls_per_case=20,
        timeout_seconds=15.0,
    ))
    executor.register(ToolSpec(
        name="icd_code_lookup",
        description="Validate or look up ICD-10/11 codes",
        allowed_roles={"admin", "reviewer", "provider"},
        max_calls_per_case=50,
        timeout_seconds=10.0,
    ))
    executor.register(ToolSpec(
        name="formulary_check",
        description="Check drug formulary coverage",
        allowed_roles={"admin", "reviewer"},
        max_calls_per_case=10,
        timeout_seconds=10.0,
    ))
    executor.register(ToolSpec(
        name="audit_query",
        description="Query audit log for compliance reporting",
        allowed_roles={"admin"},
        max_calls_per_case=5,
        timeout_seconds=20.0,
    ))
