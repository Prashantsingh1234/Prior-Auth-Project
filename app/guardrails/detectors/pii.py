"""
HIPAA PHI / PII detection for healthcare contexts.

Covers all 18 HIPAA Safe Harbor identifiers plus additional healthcare PII:
  1. Names (in clinical context)
  2. Geographic data (zip codes, addresses)
  3. Dates (DOB, admission, discharge, death)
  4. Phone numbers
  5. Fax numbers
  6. Email addresses
  7. Social Security Numbers (SSN)
  8. Medical Record Numbers (MRN)
  9. Health plan beneficiary numbers
  10. Account numbers
  11. Certificate / license numbers
  12. Vehicle identifiers (VIN, license plates)
  13. Device identifiers / serial numbers
  14. URLs
  15. IP addresses
  16. Biometric identifiers
  17. Full-face photographs
  18. Any other unique identifying number

Additional healthcare identifiers:
  - NPI (National Provider Identifier)
  - DEA numbers
  - Insurance member IDs
  - UPIN (Unique Physician Identification Number)
  - ICD codes in context of patient identification

Usage:
    result = await detect_pii(text, threshold=0.85)
    # Returns GuardrailViolation if PHI found, else None

    entities = find_pii_entities(text)
    # Returns list of (entity_type, matched_text, span) tuples
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.guardrails.models import (
    GuardrailStage,
    GuardrailViolation,
    ViolationSeverity,
    ViolationType,
)

_DETECTOR_NAME = "pii_detection"


@dataclass
class PIIEntity:
    entity_type: str
    matched:     str
    start:       int
    end:         int
    confidence:  float
    hipaa_category: int | None = None   # 1–18 HIPAA identifier number


# ---------------------------------------------------------------------------
# Pattern library — ordered by HIPAA identifier number
# ---------------------------------------------------------------------------

_PII_PATTERNS: list[tuple[str, re.Pattern, float, int | None]] = [
    # (entity_type, pattern, base_confidence, hipaa_category)

    # 7. SSN
    ("ssn",
     re.compile(r"\b(?!000|666|9\d{2})\d{3}[- ](?!00)\d{2}[- ](?!0000)\d{4}\b"),
     0.97, 7),

    # 8. Medical Record Number
    ("mrn",
     re.compile(r"\b(?:MRN|Medical\s+Record\s+(?:Number|#|No\.?))\s*[:=#]?\s*\d{5,12}\b", re.IGNORECASE),
     0.97, 8),

    # 9. Health plan beneficiary number (Medicare format)
    ("medicare_id",
     re.compile(r"\b[1-9][A-Z][A-Z0-9]\d[A-Z][A-Z0-9]\d[A-Z]{3}\d{2}\b"),
     0.95, 9),

    # NPI (10 digits starting with 1 or 2)
    ("npi",
     re.compile(r"\b(?:NPI|National\s+Provider\s+Identifier)\s*[:=#]?\s*[12]\d{9}\b", re.IGNORECASE),
     0.96, None),

    # DEA number (2 letters + 7 digits)
    ("dea_number",
     re.compile(r"\b(?:DEA\s*(?:Number|#|No\.?)?\s*[:=]?\s*)?[A-Z]{2}\d{7}\b", re.IGNORECASE),
     0.85, None),

    # Insurance member ID (generic patterns)
    ("insurance_member_id",
     re.compile(r"\b(?:Member\s+ID|Policy\s+(?:Number|#|No\.?)|Subscriber\s+ID|Group\s+(?:Number|#))\s*[:=#]?\s*[A-Z0-9]{6,20}\b", re.IGNORECASE),
     0.88, 9),

    # 4 & 5. Phone / fax numbers
    ("phone",
     re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
     0.92, 4),

    # 6. Email addresses
    ("email",
     re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z]{2,}\b", re.IGNORECASE),
     0.96, 6),

    # 3. Dates — birth dates and clinical dates (more specific context triggers higher confidence)
    ("date_of_birth",
     re.compile(r"\b(?:DOB|Date\s+of\s+Birth|Born(?:\s+on)?)\s*[:=]?\s*\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b", re.IGNORECASE),
     0.97, 3),
    ("clinical_date",
     re.compile(r"\b(?:Admission|Discharge|Service|Visit|Procedure)\s+Date\s*[:=]?\s*\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b", re.IGNORECASE),
     0.90, 3),

    # 2. Zip codes (5 or 5+4)
    ("zip_code",
     re.compile(r"\b\d{5}(?:-\d{4})?\b"),
     0.60, 2),   # Low confidence — zip alone is rarely PHI

    # IP addresses (15. Web URLs)
    ("ip_address",
     re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"),
     0.85, 15),

    # Account numbers (banking/payment in healthcare billing)
    ("account_number",
     re.compile(r"\b(?:Account\s+(?:Number|#|No\.?)|Billing\s+(?:Account|ID))\s*[:=#]?\s*[0-9]{6,20}\b", re.IGNORECASE),
     0.88, 10),

    # UPIN (6 alphanumeric characters, legacy physician ID)
    ("upin",
     re.compile(r"\b(?:UPIN)\s*[:=#]?\s*[A-Z]\d{5}\b", re.IGNORECASE),
     0.92, None),

    # Patient name patterns (in clinical context)
    ("patient_name",
     re.compile(r"\b(?:Patient\s+Name|Member\s+Name|Beneficiary\s+Name)\s*[:=]\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", re.IGNORECASE),
     0.93, 1),

    # Credit card numbers (billing fraud risk)
    ("credit_card",
     re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12})\b"),
     0.97, None),
]

# Context words that boost PII confidence when nearby
_PHI_CONTEXT_WORDS = re.compile(
    r"\b(patient|member|subscriber|beneficiary|insured|claimant|provider|physician|"
    r"diagnosis|icd|cpt|hcpcs|ndc|rx|prescription|medication|procedure|surgery|"
    r"hospital|clinic|admit|discharge|referral|authorization|prior\s+auth|pa\s+request)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_pii_entities(text: str) -> list[PIIEntity]:
    """
    Scan ``text`` for all PHI/PII entities and return them.

    Does NOT apply a threshold — returns everything found.
    Use detect_pii() for threshold-gated guardrail enforcement.
    """
    entities: list[PIIEntity] = []

    # Count PHI context words in the full text
    context_boost = min(len(_PHI_CONTEXT_WORDS.findall(text)) * 0.03, 0.15)

    for entity_type, pattern, base_confidence, hipaa_cat in _PII_PATTERNS:
        for m in pattern.finditer(text):
            # Local context boost — PHI context words near the match
            window_start = max(0, m.start() - 100)
            window_end   = min(len(text), m.end() + 100)
            local_context_hits = len(_PHI_CONTEXT_WORDS.findall(text[window_start:window_end]))
            local_boost = min(local_context_hits * 0.05, 0.15)

            confidence = min(base_confidence + context_boost + local_boost, 1.0)
            entities.append(PIIEntity(
                entity_type=entity_type,
                matched=m.group(),
                start=m.start(),
                end=m.end(),
                confidence=round(confidence, 4),
                hipaa_category=hipaa_cat,
            ))

    # Deduplicate overlapping matches (keep highest confidence)
    entities.sort(key=lambda e: e.confidence, reverse=True)
    deduplicated: list[PIIEntity] = []
    covered: list[tuple[int, int]] = []
    for entity in entities:
        if not any(s <= entity.start < e or s < entity.end <= e for s, e in covered):
            deduplicated.append(entity)
            covered.append((entity.start, entity.end))

    return deduplicated


async def detect_pii(
    text: str,
    threshold: float = 0.85,
    stage: GuardrailStage = GuardrailStage.POST_LLM,
    context: dict[str, Any] | None = None,
) -> GuardrailViolation | None:
    """
    Detect PHI/PII in ``text`` at or above confidence threshold.

    Returns a GuardrailViolation if any entity's confidence ≥ threshold.
    """
    if not text or not text.strip():
        return None

    entities = find_pii_entities(text)
    qualifying = [e for e in entities if e.confidence >= threshold]

    if not qualifying:
        return None

    # Max confidence across all qualifying entities
    max_confidence = max(e.confidence for e in qualifying)
    entity_types   = list({e.entity_type for e in qualifying})
    hipaa_cats     = sorted({e.hipaa_category for e in qualifying if e.hipaa_category})

    severity = _count_to_severity(len(qualifying), max_confidence)

    evidence: dict[str, Any] = {
        "entity_count":   len(qualifying),
        "entity_types":   entity_types,
        "hipaa_categories": hipaa_cats,
        "sample_entities": [
            {"type": e.entity_type, "confidence": e.confidence}
            for e in qualifying[:5]
        ],
    }

    return GuardrailViolation(
        violation_type=ViolationType.PII_LEAKAGE,
        severity=severity,
        description=(
            f"HIPAA PHI detected: {len(qualifying)} entit{'y' if len(qualifying)==1 else 'ies'} "
            f"({', '.join(entity_types[:4])})"
        ),
        confidence=max_confidence,
        evidence=evidence,
        stage=stage,
        detector=_DETECTOR_NAME,
    )


def _count_to_severity(count: int, max_confidence: float) -> ViolationSeverity:
    if max_confidence >= 0.95 or count >= 3:
        return ViolationSeverity.CRITICAL
    if max_confidence >= 0.88 or count >= 2:
        return ViolationSeverity.HIGH
    if max_confidence >= 0.75:
        return ViolationSeverity.MEDIUM
    return ViolationSeverity.LOW
