"""
Guardrail policy configuration.

GuardrailPolicy is the single authoritative configuration object for the
entire guardrail pipeline.  Policies are loaded from settings at startup
and can be overridden per-node or per-domain.

Three built-in policies are provided:
  DEFAULT_POLICY      — balanced; suitable for most nodes
  STRICT_POLICY       — maximum enforcement; used for reasoning / decision nodes
  LENIENT_POLICY      — reduced thresholds; for ingestion / document parsing nodes

Custom policies can be built with GuardrailPolicy.custom(...).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.guardrails.models import ViolationSeverity, ViolationType


@dataclass(frozen=True)
class DetectorThresholds:
    """Per-detector confidence thresholds.  Violations below threshold are ignored."""

    prompt_injection:     float = 0.70   # Fire if injection confidence ≥ this
    jailbreak:            float = 0.80
    pii_detection:        float = 0.85   # High bar — PHI false-positives are disruptive
    output_safety:        float = 0.75
    policy_grounding:     float = 0.60   # Minimum citation coverage required
    retrieval_anomaly:    float = 0.70   # Cosine distance anomaly score
    schema_violation:     float = 0.00   # Schema violations are binary (always fire)
    tool_abuse:           float = 0.80
    output_moderation:    float = 0.75


@dataclass(frozen=True)
class EscalationPolicy:
    """
    Rules for automatic blocking and reviewer escalation.

    auto_block_severities:
        Violations of these severities immediately block the request without
        waiting for a human decision.

    escalate_severities:
        Violations of these severities notify a human reviewer but do not
        automatically block (unless combined_block_count is reached).

    combined_block_count:
        Block automatically if this many MEDIUM+ violations occur in one check,
        even if no individual violation meets the auto-block threshold.

    fallback_response:
        What to return to the caller when the request is blocked.
    """

    auto_block_severities:   frozenset[ViolationSeverity] = field(
        default_factory=lambda: frozenset({ViolationSeverity.CRITICAL, ViolationSeverity.HIGH})
    )
    escalate_severities:     frozenset[ViolationSeverity] = field(
        default_factory=lambda: frozenset({ViolationSeverity.MEDIUM, ViolationSeverity.HIGH, ViolationSeverity.CRITICAL})
    )
    combined_block_count:    int = 3
    fallback_response:       str = (
        "This request could not be processed due to a security policy violation. "
        "Your case has been escalated to a human reviewer."
    )
    escalation_target:       str = "reviewer"   # "reviewer" | "admin" | "security_team"
    notify_on_escalation:    bool = True


@dataclass(frozen=True)
class SanitizerConfig:
    """What the pipeline is allowed to sanitize vs. must block."""

    sanitize_pii_in_output:   bool = True    # Mask PHI before returning to caller
    sanitize_pii_in_prompts:  bool = True    # Mask PHI in prompts before LLM call
    allow_partial_sanitize:   bool = True    # Return sanitized result instead of hard block
    max_pii_entities_allowed: int = 0        # 0 = no PHI in output ever


@dataclass(frozen=True)
class GuardrailPolicy:
    """
    Complete guardrail configuration for one pipeline stage or node.

    Attributes
    ----------
    name:               Human-readable label for logging.
    enabled_detectors:  Which detectors to run (None = all).
    thresholds:         Per-detector confidence cutoffs.
    escalation:         Blocking and escalation rules.
    sanitizer:          Content sanitization rules.
    evaluator_aware:    When True, routing decisions from the evaluation
                        framework can demote models that repeatedly trigger
                        guardrails.
    """

    name:               str
    enabled_detectors:  frozenset[ViolationType] | None = None   # None = all
    thresholds:         DetectorThresholds = field(default_factory=DetectorThresholds)
    escalation:         EscalationPolicy   = field(default_factory=EscalationPolicy)
    sanitizer:          SanitizerConfig    = field(default_factory=SanitizerConfig)
    evaluator_aware:    bool = True

    def detector_enabled(self, vtype: ViolationType) -> bool:
        """Return True if the given detector should run under this policy."""
        return self.enabled_detectors is None or vtype in self.enabled_detectors

    def should_block(self, severity: ViolationSeverity) -> bool:
        return severity in self.escalation.auto_block_severities

    def should_escalate(self, severity: ViolationSeverity) -> bool:
        return severity in self.escalation.escalate_severities

    @classmethod
    def custom(
        cls,
        name: str,
        **overrides: Any,
    ) -> "GuardrailPolicy":
        """Build a custom policy by overriding specific fields of DEFAULT_POLICY."""
        base_fields = {
            "name": name,
            "enabled_detectors": None,
            "thresholds": DetectorThresholds(),
            "escalation": EscalationPolicy(),
            "sanitizer": SanitizerConfig(),
            "evaluator_aware": True,
        }
        base_fields.update(overrides)
        return cls(**base_fields)


# ---------------------------------------------------------------------------
# Built-in policies
# ---------------------------------------------------------------------------

#: Balanced policy suitable for most workflow nodes
DEFAULT_POLICY = GuardrailPolicy(name="default")

#: Maximum enforcement — reasoning and decision nodes
STRICT_POLICY = GuardrailPolicy(
    name="strict",
    thresholds=DetectorThresholds(
        prompt_injection=0.55,
        jailbreak=0.60,
        pii_detection=0.75,
        output_safety=0.60,
        policy_grounding=0.70,
        retrieval_anomaly=0.55,
        tool_abuse=0.65,
        output_moderation=0.60,
    ),
    escalation=EscalationPolicy(
        auto_block_severities=frozenset({
            ViolationSeverity.CRITICAL,
            ViolationSeverity.HIGH,
            ViolationSeverity.MEDIUM,
        }),
        combined_block_count=2,
    ),
    sanitizer=SanitizerConfig(
        max_pii_entities_allowed=0,
        allow_partial_sanitize=False,
    ),
)

#: Relaxed policy for document ingestion / OCR nodes (PHI may legitimately appear)
LENIENT_POLICY = GuardrailPolicy(
    name="lenient",
    enabled_detectors=frozenset({
        ViolationType.PROMPT_INJECTION,
        ViolationType.JAILBREAK,
        ViolationType.TOOL_ABUSE,
        ViolationType.SCHEMA_VIOLATION,
    }),
    thresholds=DetectorThresholds(
        prompt_injection=0.85,
        jailbreak=0.90,
        tool_abuse=0.90,
    ),
    escalation=EscalationPolicy(
        auto_block_severities=frozenset({ViolationSeverity.CRITICAL}),
        escalate_severities=frozenset({ViolationSeverity.HIGH, ViolationSeverity.CRITICAL}),
    ),
    sanitizer=SanitizerConfig(
        sanitize_pii_in_output=False,   # Ingestion nodes need raw PHI for extraction
        sanitize_pii_in_prompts=False,
    ),
)

#: Node → policy mapping (overridden per-deployment via settings)
NODE_POLICY_MAP: dict[str, GuardrailPolicy] = {
    "ingestion_node":      LENIENT_POLICY,
    "extraction_node":     DEFAULT_POLICY,
    "retrieval_node":      DEFAULT_POLICY,
    "reasoning_node":      STRICT_POLICY,
    "clarification_node":  DEFAULT_POLICY,
    "human_review_node":   DEFAULT_POLICY,
    "decision_node":       STRICT_POLICY,
    "audit_node":          LENIENT_POLICY,
}


def get_policy_for_node(node_name: str) -> GuardrailPolicy:
    """Return the GuardrailPolicy registered for the given node, or DEFAULT."""
    return NODE_POLICY_MAP.get(node_name, DEFAULT_POLICY)
