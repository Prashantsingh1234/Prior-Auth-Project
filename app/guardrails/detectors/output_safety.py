"""
Unsafe / hallucinated medical output detector.

Checks LLM-generated text for:
  - Fabricated drug dosages or medication instructions
  - Clinical misinformation (contraindicated treatments)
  - Ungrounded medical claims (facts without citations)
  - Off-label procedure recommendations beyond scope
  - Dangerous approval/denial recommendations without evidence
  - Toxic / threatening / discriminatory content
"""

from __future__ import annotations

import re
from typing import Any

from app.guardrails.models import (
    GuardrailStage,
    GuardrailViolation,
    ViolationSeverity,
    ViolationType,
)

_DETECTOR_NAME = "output_safety"


# ---------------------------------------------------------------------------
# Medical hallucination patterns
# ---------------------------------------------------------------------------

# Drug dosage assertions without source — LLM hallucinating specific numbers
_DOSAGE_HALLUCINATION: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"\b(?:dose|dosage|administer|prescribe|take)\s+\d+\s*(?:mg|mcg|ml|g|units?|IU|meq)\b",
    r"\b\d+\s*(?:mg|mcg|ml|g|units?|IU)\s+(?:of\s+)?(?:every|per|each|bid|tid|qid|qd|prn)\b",
    r"\b(?:maximum|minimum|recommended|usual|standard)\s+dose\s+(?:is|of|for)\s+\d+\s*(?:mg|mcg|g)\b",
    r"\b(?:loading\s+dose|maintenance\s+dose|titrate\s+(?:up|down)\s+to)\s+\d+\s*(?:mg|mcg)\b",
]]

# Absolute clinical assertions without hedging
_UNSUPPORTED_CLINICAL_CLAIMS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"\b(?:this\s+(?:drug|medication|treatment|procedure)\s+(?:will|shall|guarantees?))\b",
    r"\b(?:clinically\s+proven|scientifically\s+proven|medically\s+established)\s+to\s+(?:cure|treat|prevent|eliminate)\b",
    r"\b(?:there\s+is\s+no\s+need\s+for|not\s+medically\s+necessary|unnecessary\s+(?:procedure|treatment|medication))\b",
    r"\b(?:100\s*%|always|never|guaranteed|certain)\s+(?:effective|safe|appropriate|necessary)\b",
    r"\bapprove\s+this\s+request\s+(?:immediately|right\s+away|without\s+(?:review|question))\b",
    r"\bdeny\s+this\s+(?:claim|request|authorization)\s+(?:immediately|outright)\s+(?:without|regardless)\b",
]]

# Content moderation — output that should never appear in PA decisions
_TOXIC_CONTENT: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"\b(?:kill|murder|harm|hurt|attack|destroy|eliminate)\s+(?:the\s+)?(?:patient|member|claimant|provider|doctor)\b",
    r"\b(?:you\s+(?:should|must|need\s+to)\s+(?:die|suffer|be\s+punished))\b",
    r"\b(?:racist|sexist|discriminatory)\s+(?:decision|reason|denial|approval)\b",
    r"\bdenied\s+(?:because|due\s+to|based\s+on)\s+(?:race|gender|religion|age|disability|ethnicity|nationality)\b",
]]

# Scope violations — PA AI making recommendations beyond its authorization
_SCOPE_VIOLATIONS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"\b(?:I\s+recommend|my\s+recommendation\s+is|you\s+should)\s+(?:see\s+a\s+)?(?:doctor|physician|specialist|surgeon)\b",
    r"\b(?:I\s+(?:diagnose|diagnosed|am\s+diagnosing))\b",
    r"\b(?:in\s+my\s+medical\s+opinion|as\s+a\s+medical\s+professional)\b",
    r"\bthis\s+(?:patient|member)\s+(?:has|suffers\s+from|is\s+diagnosed\s+with)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+(?:disease|disorder|syndrome|condition)\b",
    r"\bprescribe\s+(?:this\s+)?(?:patient|member|them)\s+\w+",
]]

# Confidence-inflating hedging bypass
_OVERCONFIDENCE_SIGNALS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"\bI\s+am\s+(?:absolutely|100\s*%|completely|totally|fully)\s+(?:certain|sure|confident|positive)\b",
    r"\b(?:without\s+(?:a\s+)?doubt|unquestionably|indisputably|undeniably)\b",
    r"\b(?:no\s+further\s+review\s+(?:is\s+)?needed|no\s+additional\s+information\s+(?:is\s+)?required)\b",
]]


async def detect_unsafe_output(
    text: str,
    threshold: float = 0.75,
    stage: GuardrailStage = GuardrailStage.POST_LLM,
    context: dict[str, Any] | None = None,
) -> GuardrailViolation | None:
    """
    Detect unsafe, hallucinated, or scope-violating content in LLM output.

    Returns a GuardrailViolation if confidence ≥ threshold, else None.
    """
    if not text or not text.strip():
        return None

    evidence: dict[str, Any] = {"categories": [], "signals": []}
    max_score = 0.0

    def _check(patterns: list[re.Pattern], category: str, base_score: float) -> float:
        hits = [p for p in patterns if p.search(text)]
        if hits:
            evidence["categories"].append(category)
            evidence["signals"].extend([p.pattern[:60] for p in hits[:2]])
            return base_score + (len(hits) - 1) * 0.05
        return 0.0

    scores = [
        _check(_TOXIC_CONTENT,                "toxic_content",          0.95),
        _check(_DOSAGE_HALLUCINATION,         "dosage_hallucination",   0.72),
        _check(_UNSUPPORTED_CLINICAL_CLAIMS,  "unsupported_claims",     0.68),
        _check(_SCOPE_VIOLATIONS,             "scope_violation",        0.78),
        _check(_OVERCONFIDENCE_SIGNALS,       "overconfidence",         0.55),
    ]
    max_score = max(scores) if scores else 0.0
    confidence = min(round(max_score, 4), 1.0)

    if confidence < threshold:
        return None

    if "toxic_content" in evidence["categories"]:
        severity = ViolationSeverity.CRITICAL
    elif confidence >= 0.85:
        severity = ViolationSeverity.HIGH
    elif confidence >= 0.70:
        severity = ViolationSeverity.MEDIUM
    else:
        severity = ViolationSeverity.LOW

    evidence["text_preview"] = text[:300]

    return GuardrailViolation(
        violation_type=ViolationType.UNSAFE_OUTPUT,
        severity=severity,
        description=f"Unsafe output detected: {', '.join(evidence['categories'])}",
        confidence=confidence,
        evidence=evidence,
        stage=stage,
        detector=_DETECTOR_NAME,
    )
