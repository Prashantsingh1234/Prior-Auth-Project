"""
app.guardrails — Enterprise healthcare AI guardrail framework.

Public API
----------
GuardrailPipeline               Main entry point; one per node
  .for_node(node_name, ...)     Factory using registered node policy
  .check_input(prompt, state)   Pre-LLM: injection, jailbreak, PII
  .check_output(output, state)  Post-LLM: safety, grounding, schema, PII
  .check_retrieval(docs)        Retrieval poisoning detection

GuardrailResult                 Aggregated pipeline result
GuardrailViolation              Single detected violation
ViolationType                   Enum of all violation categories
ViolationSeverity               Enum: LOW / MEDIUM / HIGH / CRITICAL
GuardrailStage                  Enum: PRE_LLM / POST_LLM / etc.
EscalationEvent                 Security escalation record

GuardrailPolicy                 Configuration snapshot
DEFAULT_POLICY                  Balanced policy (most nodes)
STRICT_POLICY                   Maximum enforcement (reasoning/decision)
LENIENT_POLICY                  Reduced enforcement (ingestion/OCR)
get_policy_for_node(name)       Lookup registered node policy

EscalationEngine                Manages violation escalation lifecycle
get_escalation_engine()         Singleton accessor

SecureToolExecutor              Sandboxed LLM tool execution
get_tool_executor()             Singleton accessor

GuardrailMiddleware             Starlette HTTP middleware (fast layer)
"""

from app.guardrails.config import (
    DEFAULT_POLICY,
    LENIENT_POLICY,
    STRICT_POLICY,
    GuardrailPolicy,
    get_policy_for_node,
)
from app.guardrails.escalation import EscalationEngine, get_escalation_engine
from app.guardrails.middleware import GuardrailMiddleware
from app.guardrails.models import (
    EscalationEvent,
    GuardrailResult,
    GuardrailStage,
    GuardrailViolation,
    ViolationSeverity,
    ViolationType,
)
from app.guardrails.pipeline import GuardrailPipeline
from app.guardrails.tool_executor import SecureToolExecutor, get_tool_executor

__all__ = [
    # Pipeline
    "GuardrailPipeline",
    # Models
    "GuardrailResult",
    "GuardrailViolation",
    "ViolationType",
    "ViolationSeverity",
    "GuardrailStage",
    "EscalationEvent",
    # Config
    "GuardrailPolicy",
    "DEFAULT_POLICY",
    "STRICT_POLICY",
    "LENIENT_POLICY",
    "get_policy_for_node",
    # Escalation
    "EscalationEngine",
    "get_escalation_engine",
    # Tool executor
    "SecureToolExecutor",
    "get_tool_executor",
    # Middleware
    "GuardrailMiddleware",
]
