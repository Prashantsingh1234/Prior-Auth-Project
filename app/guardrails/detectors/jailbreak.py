"""
Jailbreak detector.

Distinguishes jailbreaks from prompt injection:
  - Prompt injection: adversary hijacks the LLM's instruction context
  - Jailbreak: adversary persuades the LLM to violate its own safety rules

Healthcare jailbreak vectors:
  - Claiming clinical emergency to bypass PA review
  - Framing harmful requests as hypothetical medical education
  - Using fictional patient scenarios to extract real PHI handling paths
  - Impersonating CMS / HHS to override policy decisions
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

_DETECTOR_NAME = "jailbreak"


# ---------------------------------------------------------------------------
# Pattern library
# ---------------------------------------------------------------------------

_ROLEPLAY_JAILBREAKS: list[re.Pattern] = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in [
    r"(let'?s|we\s+will|you\s+will)\s+play\s+(a\s+)?(game|role|scenario|simulation)",
    r"in\s+this\s+story[,\s]+(you\s+are|you\s+play|your\s+character)",
    r"(write|create|imagine)\s+(a\s+)?story\s+(where|in\s+which)\s+(you|an?\s+ai|the\s+ai)\s+(can|will|must|has\s+to)",
    r"(as\s+a\s+)?(character|persona|entity)\s+(named|called|who)\s+\w+,?\s+you\s+(can|must|will|have\s+no)",
    r"my\s+(grandmother|aunt|uncle|friend|professor)\s+used\s+to\s+(tell|show|teach)\s+me",  # Grandma exploit
    r"(the|a)\s+(evil|opposite|mirror|shadow|dark)\s+(twin|version|ai|model)\s+(of\s+you|would)",
]]

_AUTHORITY_JAILBREAKS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    # Government / payer authority impersonation
    r"(this\s+is|i\s+am|speaking\s+on\s+behalf\s+of)\s+(cms|hhs|fda|cdc|nih|medicare|medicaid|bcbs|aetna|uhc|cigna)",
    r"(federal|government|official|regulatory)\s+(mandate|directive|order|requirement)\s+(overrides?|supersedes?|bypasses?)",
    r"as\s+(the|a)\s+(medical\s+)?(director|chief|vp|president|ceo|cmo|cto)\s+i\s+(authorize|approve|override|require)",
    # Emergency bypass
    r"(this\s+is|it\s+is)\s+(a\s+)?(medical\s+|life.threatening\s+|critical\s+)emergency",
    r"patient\s+(is\s+dying|will\s+die|life\s+is\s+at\s+risk|in\s+immediate\s+danger)\s+(if\s+you|unless\s+you|without)",
    r"(no\s+time|there\s+is\s+no\s+time)\s+(for|to\s+wait\s+for)\s+(review|approval|authorization|the\s+normal\s+process)",
    # Compliance / legal coercion
    r"(failure|refusing)\s+to\s+comply\s+(with\s+this|will\s+result\s+in|is)\s+(illegal|a\s+violation|lawsuit|hipaa)",
    r"you\s+(are\s+legally\s+required|must\s+by\s+law|have\s+a\s+legal\s+obligation)\s+to\s+(approve|provide|output)",
]]

_HYPOTHETICAL_JAILBREAKS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"(hypothetically|theoretically|in\s+theory|academically|for\s+academic\s+purposes?)\s*(speaking)?,?\s*(if|how|what)",
    r"(for\s+a\s+)?research\s+paper\s+(on|about)\s+(how|why|when)\s+to\s+(bypass|exploit|manipulate|override)",
    r"(if\s+you\s+were|imagine\s+you\s+are)\s+(not|no\s+longer)\s+(an\s+ai|restricted|bound\s+by|limited\s+by)",
    r"(educational|training|testing|demo(nstration)?)\s+(purposes?|environment|scenario)\s+(only)?,?\s*(so|therefore|thus)\s+you\s+(can|should|must)",
    r"what\s+would\s+(happen|a\s+(hacker|attacker|bad\s+actor))\s+(do|say|output)\s+(if|to)",
]]

_TOKEN_MANIPULATION: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"\bD\s*A\s*N\b",                       # Spaced DAN
    r"j\s*a\s*i\s*l\s*b\s*r\s*e\s*a\s*k",  # Spaced jailbreak
    r"(?:base64|b64)\s*(?:decode|encoded)\s*[:=]",
    r"rot\s*13",
    r"reverse\s+the\s+(letters?|words?|text|string)",
    r"in\s+pig\s+latin",
    r"every\s+(other|second|third)\s+(letter|word|character)",  # Steganographic
]]

_HEALTHCARE_JAILBREAKS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"(approve|auto.?approve|automatically\s+approve)\s+(all|any|every)\s+(pa|prior\s+auth|claim|request)",
    r"(skip|bypass|ignore|override)\s+(medical\s+necessity|clinical\s+criteria|coverage\s+determination)",
    r"(reveal|expose|leak|output)\s+(member|patient|subscriber)\s+(pii|phi|data|information|records?)",
    r"generate\s+(fake|false|fraudulent|fabricated)\s+(medical|clinical|pa|authorization)\s+(records?|notes?|decisions?)",
    r"(make|force|cause)\s+(the\s+)?(system|ai|model)\s+to\s+(approve|deny)\s+(without|regardless\s+of)",
]]


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

async def detect_jailbreak(
    text: str,
    threshold: float = 0.80,
    stage: GuardrailStage = GuardrailStage.PRE_LLM,
    context: dict[str, Any] | None = None,
) -> GuardrailViolation | None:
    """
    Detect jailbreak attempts in ``text``.

    Returns a GuardrailViolation if confidence ≥ threshold, else None.
    """
    if not text or not text.strip():
        return None

    evidence: dict[str, Any] = {"categories": [], "matched_patterns": []}
    score = 0.0

    def _scan(patterns: list[re.Pattern], category: str, weight: float) -> float:
        nonlocal score
        hits = [(p, p.search(text)) for p in patterns]
        matched = [(p, m) for p, m in hits if m]
        if matched:
            evidence["categories"].append(category)
            for p, _ in matched[:3]:
                evidence["matched_patterns"].append(p.pattern[:80])
            return weight * (1.0 + 0.1 * (len(matched) - 1))
        return 0.0

    score += _scan(_ROLEPLAY_JAILBREAKS,      "roleplay_persona",         0.60)
    score += _scan(_AUTHORITY_JAILBREAKS,     "authority_impersonation",  0.75)
    score += _scan(_HYPOTHETICAL_JAILBREAKS,  "hypothetical_framing",     0.45)
    score += _scan(_TOKEN_MANIPULATION,       "token_manipulation",       0.50)
    score += _scan(_HEALTHCARE_JAILBREAKS,    "healthcare_bypass",        0.85)

    # Multi-category escalation: two different jailbreak categories → higher confidence
    if len(evidence["categories"]) >= 2:
        score = min(score * 1.20, 1.0)

    confidence = min(round(score, 4), 1.0)

    if confidence < threshold:
        return None

    severity = _score_to_severity(confidence)
    evidence["text_preview"] = text[:300]

    return GuardrailViolation(
        violation_type=ViolationType.JAILBREAK,
        severity=severity,
        description=f"Jailbreak attempt detected (confidence={confidence:.2f}, categories={evidence['categories']})",
        confidence=confidence,
        evidence=evidence,
        stage=stage,
        detector=_DETECTOR_NAME,
    )


def _score_to_severity(score: float) -> ViolationSeverity:
    if score >= 0.85:
        return ViolationSeverity.CRITICAL
    if score >= 0.70:
        return ViolationSeverity.HIGH
    if score >= 0.50:
        return ViolationSeverity.MEDIUM
    return ViolationSeverity.LOW
