"""
Prompt injection detector.

Uses a two-stage approach:
  1. Fast regex pattern matching against known injection signatures
  2. Heuristic scoring (keyword density, structural anomalies, encoding tricks)

Returns a GuardrailViolation when confidence ≥ policy threshold.

Healthcare-specific additions:
  - Detects attempts to override clinical decision guidelines
  - Catches "I am a doctor / nurse / administrator" authority escalation
  - Flags requests to output raw system prompts or policy documents
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

_DETECTOR_NAME = "prompt_injection"


# ---------------------------------------------------------------------------
# Pattern library
# ---------------------------------------------------------------------------

# High-confidence signatures — any single match scores ≥ 0.85
_CRITICAL_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    # Classic instruction overrides
    r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|context|rules?)",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?)",
    r"forget\s+(everything|all)\s+(you|i)\s+(were|was|have\s+been)\s+told",
    r"new\s+instructions?\s*[:;]",
    r"your\s+(new|actual|real|true)\s+(instructions?|role|task|purpose)\s*(are|is)\s*[:;]",
    # System prompt extraction
    r"(print|show|output|reveal|display|tell\s+me|what\s+is)\s+(your\s+)?(system\s+prompt|initial\s+prompt|instructions?|directives?)",
    r"repeat\s+(the\s+)?(text|words|content)\s+(above|before|earlier|at\s+the\s+beginning)",
    r"what\s+(were|are)\s+your\s+(original\s+)?(instructions?|guidelines?|rules?)",
    # Role injection
    r"you\s+are\s+now\s+(a\s+|an\s+)?(different|new|unrestricted|free|jailbroken)",
    r"act\s+as\s+(if\s+you\s+(are|were)\s+)?(a\s+|an\s+)?(different|new|unrestricted|evil|unfiltered)",
    r"pretend\s+(you\s+are|to\s+be)\s+(a\s+|an\s+)?(different|unrestricted|evil)",
    # Prompt delimiters
    r"(```|<\|im_end\|>|<\|endoftext\|>|\[INST\]|<<SYS>>)\s*(ignore|new|forget|disregard)",
    # Healthcare-specific overrides
    r"override\s+(clinical|medical|pa|prior\s+auth|insurance)\s+(guidelines?|rules?|policies?|decisions?)",
    r"(approve|deny|override)\s+(this\s+)?(claim|request|authorization|pa)\s+without\s+(review|checking|validating)",
    r"bypass\s+(medical|clinical|safety|policy)\s+(review|check|validation|guidelines?)",
]]

# Medium-confidence patterns — score increases with multiple matches
_MEDIUM_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"\bDAN\b",                              # Do Anything Now jailbreak
    r"developer\s+mode",
    r"jailbreak(ed|ing)?",
    r"no\s+restrictions?",
    r"without\s+(any\s+)?(restrictions?|limits?|filters?|guardrails?)",
    r"(ignore|skip|bypass)\s+(safety|ethical|moral|clinical)\s+(guidelines?|rules?|restrictions?)",
    r"for\s+(research|educational|testing|fictional|hypothetical)\s+purposes?\s+(only)?,?\s+(you\s+can|you\s+must|please)",
    r"in\s+this\s+(fictional|hypothetical|roleplay|simulation)\s+(scenario|world|context|universe)",
    r"as\s+(a\s+)?(fictional|hypothetical)\s+character",
    r"tell\s+me\s+(how|the\s+steps|instructions?)\s+to\s+(hack|exploit|compromise|bypass)",
    r"(system|admin|root|superuser)\s+(access|privileges?|override|mode)",
    # Authority escalation (healthcare-specific)
    r"i\s+am\s+(a\s+|an\s+)?(doctor|physician|nurse|pharmacist|administrator|ceo|compliance\s+officer)",
    r"as\s+(a\s+|an\s+)?(licensed|certified|registered)\s+(medical|healthcare|clinical)\s+(professional|provider|practitioner)",
    r"on\s+behalf\s+of\s+(the\s+)?(hospital|clinic|insurance\s+company|cms|hhs|medicare|medicaid)",
]]

# Structural anomaly patterns
_STRUCTURAL_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in [
    r"(?:human|assistant|system)\s*:\s*",       # Fake conversation turns
    r"\[SYSTEM\]|\[USER\]|\[ASSISTANT\]",
    r"<\|system\|>|<\|user\|>|<\|assistant\|>",
    r"#{3,}\s*(instructions?|system|config)",    # Markdown header injection
    r"---+\s*\n.*?instructions?.*?\n---+",        # YAML-style injection
]]

# Encoding obfuscation
_ENCODING_PATTERNS: list[re.Pattern] = [re.compile(p) for p in [
    r"&#\d{1,5};",                # HTML entities
    r"\\u[0-9a-fA-F]{4}",        # Unicode escapes
    r"%[0-9a-fA-F]{2}",          # URL encoding
    r"(?:base64|b64)[:,\s]",     # Base64 marker
]]


# ---------------------------------------------------------------------------
# Detector function
# ---------------------------------------------------------------------------

async def detect_prompt_injection(
    text: str,
    threshold: float = 0.70,
    stage: GuardrailStage = GuardrailStage.PRE_LLM,
    context: dict[str, Any] | None = None,
) -> GuardrailViolation | None:
    """
    Analyse ``text`` for prompt injection signals.

    Returns a GuardrailViolation if confidence ≥ threshold, else None.
    """
    if not text or not text.strip():
        return None

    evidence: dict[str, Any] = {"matched_patterns": [], "heuristic_signals": []}
    confidence = 0.0

    # --- Stage 1: Critical patterns (immediate high score) ---
    for pattern in _CRITICAL_PATTERNS:
        m = pattern.search(text)
        if m:
            evidence["matched_patterns"].append(pattern.pattern[:80])
            confidence = max(confidence, 0.92)

    # --- Stage 2: Medium patterns (cumulative) ---
    medium_hits = 0
    for pattern in _MEDIUM_PATTERNS:
        if pattern.search(text):
            medium_hits += 1
            evidence["matched_patterns"].append(pattern.pattern[:80])
    if medium_hits:
        confidence = max(confidence, 0.35 + (medium_hits * 0.15))

    # --- Stage 3: Structural anomalies ---
    struct_hits = sum(1 for p in _STRUCTURAL_PATTERNS if p.search(text))
    if struct_hits:
        evidence["heuristic_signals"].append(f"structural_anomaly_count={struct_hits}")
        confidence = max(confidence, confidence + 0.15 * struct_hits)

    # --- Stage 4: Encoding obfuscation ---
    enc_hits = sum(1 for p in _ENCODING_PATTERNS if p.search(text))
    if enc_hits:
        evidence["heuristic_signals"].append(f"encoding_obfuscation_count={enc_hits}")
        confidence = min(confidence + 0.10, 1.0)

    # --- Stage 5: Instruction-to-content ratio heuristic ---
    word_count = len(text.split())
    imperative_verbs = len(re.findall(
        r"\b(ignore|disregard|forget|override|bypass|pretend|act|tell|reveal|show|print|output)\b",
        text, re.IGNORECASE,
    ))
    if word_count > 0 and imperative_verbs / word_count > 0.08:
        evidence["heuristic_signals"].append(
            f"high_imperative_ratio={imperative_verbs}/{word_count}"
        )
        confidence = min(confidence + 0.12, 1.0)

    confidence = min(round(confidence, 4), 1.0)

    if confidence < threshold:
        return None

    severity = _confidence_to_severity(confidence)
    evidence["text_preview"] = text[:300]

    return GuardrailViolation(
        violation_type=ViolationType.PROMPT_INJECTION,
        severity=severity,
        description=f"Prompt injection detected (confidence={confidence:.2f})",
        confidence=confidence,
        evidence=evidence,
        stage=stage,
        detector=_DETECTOR_NAME,
    )


def _confidence_to_severity(confidence: float) -> ViolationSeverity:
    if confidence >= 0.90:
        return ViolationSeverity.CRITICAL
    if confidence >= 0.75:
        return ViolationSeverity.HIGH
    if confidence >= 0.55:
        return ViolationSeverity.MEDIUM
    return ViolationSeverity.LOW
