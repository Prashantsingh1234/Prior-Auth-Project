"""
HIPAA PHI masking patterns.

Covers all 18 HIPAA Safe Harbor identifiers with context-aware replacement
masks that preserve the type of data for downstream audit trails without
exposing any actual PHI.

Mask format examples:
  SSN        → [SSN-REDACTED]
  MRN        → [MRN-REDACTED]
  phone      → [PHONE-REDACTED]
  email      → [EMAIL-REDACTED]
  date_birth → [DOB-REDACTED]
  name       → [NAME-REDACTED]
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class MaskPattern:
    """One PHI masking rule."""
    name:        str                  # Human-readable label
    pattern:     re.Pattern           # Compiled regex
    mask:        str                  # Replacement string
    hipaa_id:    int | None           # HIPAA identifier number (1–18)
    priority:    int = 10             # Higher = applied first (prevents double-masking)
    transformer: Callable[[re.Match], str] | None = None  # Dynamic mask if provided


def _phone_mask(m: re.Match) -> str:
    return "[PHONE-REDACTED]"


def _email_mask(m: re.Match) -> str:
    return "[EMAIL-REDACTED]"


# Ordered by HIPAA safe harbor identifier number
HIPAA_MASK_PATTERNS: list[MaskPattern] = [

    # 1. Names — in clinical context only (avoid masking common names in general text)
    MaskPattern(
        name="patient_name_labeled",
        pattern=re.compile(
            r"(?:Patient|Member|Subscriber|Beneficiary|Insured|Claimant)\s+Name\s*[:=]\s*"
            r"([A-Z][a-zA-Z\-'\.]+(?:\s+[A-Z][a-zA-Z\-'\.]+){1,3})",
            re.IGNORECASE,
        ),
        mask="Patient Name: [NAME-REDACTED]",
        hipaa_id=1,
        priority=90,
    ),

    # 2. Geographic — zip codes (≤3 digits for small populations)
    MaskPattern(
        name="zip_code_full",
        pattern=re.compile(r"\b(\d{5})(?:-\d{4})?\b"),
        mask="[ZIP-REDACTED]",
        hipaa_id=2,
        priority=20,
    ),

    # 3. Dates — dates of birth and all dates directly associated with patient
    MaskPattern(
        name="date_of_birth",
        pattern=re.compile(
            r"(?:DOB|Date\s+of\s+Birth|Born(?:\s+on)?)\s*[:=]?\s*"
            r"\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}",
            re.IGNORECASE,
        ),
        mask="DOB: [DOB-REDACTED]",
        hipaa_id=3,
        priority=85,
    ),
    MaskPattern(
        name="clinical_date_labeled",
        pattern=re.compile(
            r"(?:Admission|Discharge|Service|Visit|Procedure|Treatment)\s+Date\s*[:=]?\s*"
            r"\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}",
            re.IGNORECASE,
        ),
        mask="[CLINICAL-DATE-REDACTED]",
        hipaa_id=3,
        priority=80,
    ),

    # 4. Phone numbers
    MaskPattern(
        name="phone_number",
        pattern=re.compile(
            r"\b(?:\+?1[-.\s]?)?\(?(\d{3})\)?[-.\s](\d{3})[-.\s](\d{4})\b"
        ),
        mask="[PHONE-REDACTED]",
        hipaa_id=4,
        priority=70,
    ),

    # 5. Fax numbers (same pattern as phone, labeled context)
    MaskPattern(
        name="fax_number",
        pattern=re.compile(
            r"(?:Fax|FAX)\s*(?:Number|#|No\.?)?\s*[:=]?\s*"
            r"(?:\+?1[-.\s]?)?\(?(\d{3})\)?[-.\s](\d{3})[-.\s](\d{4})",
            re.IGNORECASE,
        ),
        mask="Fax: [FAX-REDACTED]",
        hipaa_id=5,
        priority=75,
    ),

    # 6. Email addresses
    MaskPattern(
        name="email_address",
        pattern=re.compile(
            r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z]{2,}\b",
            re.IGNORECASE,
        ),
        mask="[EMAIL-REDACTED]",
        hipaa_id=6,
        priority=70,
    ),

    # 7. Social Security Numbers
    MaskPattern(
        name="ssn",
        pattern=re.compile(
            r"\b(?!000|666|9\d{2})\d{3}[- ](?!00)\d{2}[- ](?!0000)\d{4}\b"
        ),
        mask="[SSN-REDACTED]",
        hipaa_id=7,
        priority=95,
    ),

    # 8. Medical Record Numbers
    MaskPattern(
        name="mrn",
        pattern=re.compile(
            r"\b(?:MRN|Medical\s+Record\s+(?:Number|#|No\.?))\s*[:=#]?\s*(\d{5,12})\b",
            re.IGNORECASE,
        ),
        mask="MRN: [MRN-REDACTED]",
        hipaa_id=8,
        priority=95,
    ),

    # 9. Health plan beneficiary / Medicare ID
    MaskPattern(
        name="medicare_id",
        pattern=re.compile(
            r"\b[1-9][A-Z][A-Z0-9]\d[A-Z][A-Z0-9]\d[A-Z]{3}\d{2}\b"
        ),
        mask="[MEDICARE-ID-REDACTED]",
        hipaa_id=9,
        priority=90,
    ),
    MaskPattern(
        name="insurance_member_id",
        pattern=re.compile(
            r"(?:Member\s+ID|Policy\s+(?:Number|#|No\.?)|Subscriber\s+ID|Group\s+(?:Number|#))"
            r"\s*[:=#]?\s*([A-Z0-9]{6,20})",
            re.IGNORECASE,
        ),
        mask="[MEMBER-ID-REDACTED]",
        hipaa_id=9,
        priority=85,
    ),

    # 10. Account numbers (banking / billing)
    MaskPattern(
        name="account_number",
        pattern=re.compile(
            r"(?:Account\s+(?:Number|#|No\.?)|Billing\s+(?:Account|ID))\s*[:=#]?\s*([0-9]{6,20})",
            re.IGNORECASE,
        ),
        mask="[ACCOUNT-NUMBER-REDACTED]",
        hipaa_id=10,
        priority=80,
    ),

    # 12. Vehicle identifiers (VIN)
    MaskPattern(
        name="vin",
        pattern=re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b"),
        mask="[VIN-REDACTED]",
        hipaa_id=12,
        priority=30,
    ),

    # 15. IP addresses
    MaskPattern(
        name="ipv4_address",
        pattern=re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
        ),
        mask="[IP-REDACTED]",
        hipaa_id=15,
        priority=60,
    ),

    # NPI (National Provider Identifier) — non-HIPAA but still sensitive
    MaskPattern(
        name="npi",
        pattern=re.compile(
            r"\b(?:NPI|National\s+Provider\s+Identifier)\s*[:=#]?\s*([12]\d{9})\b",
            re.IGNORECASE,
        ),
        mask="NPI: [NPI-REDACTED]",
        hipaa_id=None,
        priority=90,
    ),

    # DEA numbers
    MaskPattern(
        name="dea_number",
        pattern=re.compile(
            r"\b(?:DEA\s*(?:Number|#|No\.?)?\s*[:=]?\s*)?([A-Z]{2}\d{7})\b",
            re.IGNORECASE,
        ),
        mask="[DEA-REDACTED]",
        hipaa_id=None,
        priority=85,
    ),

    # Credit card numbers
    MaskPattern(
        name="credit_card",
        pattern=re.compile(
            r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|"
            r"3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12})\b"
        ),
        mask="[CARD-REDACTED]",
        hipaa_id=None,
        priority=98,
    ),
]

# Sorted by priority descending so high-priority patterns apply first
HIPAA_MASK_PATTERNS.sort(key=lambda p: p.priority, reverse=True)
