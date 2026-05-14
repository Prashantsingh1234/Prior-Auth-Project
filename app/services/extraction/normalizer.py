"""
Normalization utilities for extracted medical entities.

Normalization makes downstream deduplication and comparison reliable:
  - ICD codes: uppercase, insert dot if missing (E1165 → E11.65)
  - CPT codes: zero-pad to 5 digits
  - Medications: lowercase, strip trade name variants → generic name
  - Dates: best-effort ISO 8601 (YYYY-MM-DD)
  - Units: standardize unit strings (mg/dl → mg/dL)
  - Lab values: normalize test name aliases (HgB → Hemoglobin)
"""

from __future__ import annotations

import re
from datetime import datetime

import structlog
from dateutil import parser as dateutil_parser

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# ICD normalization
# ---------------------------------------------------------------------------

# Known trade name → generic name mappings (subset relevant to T2DM / CGM)
_TRADE_TO_GENERIC: dict[str, str] = {
    "ozempic": "semaglutide",
    "wegovy": "semaglutide",
    "rybelsus": "semaglutide",
    "victoza": "liraglutide",
    "saxenda": "liraglutide",
    "trulicity": "dulaglutide",
    "byetta": "exenatide",
    "bydureon": "exenatide",
    "jardiance": "empagliflozin",
    "farxiga": "dapagliflozin",
    "invokana": "canagliflozin",
    "januvia": "sitagliptin",
    "onglyza": "saxagliptin",
    "tradjenta": "linagliptin",
    "actos": "pioglitazone",
    "avandia": "rosiglitazone",
    "glucophage": "metformin",
    "lantus": "insulin glargine",
    "basaglar": "insulin glargine",
    "toujeo": "insulin glargine u-300",
    "levemir": "insulin detemir",
    "tresiba": "insulin degludec",
    "humalog": "insulin lispro",
    "novolog": "insulin aspart",
    "apidra": "insulin glulisine",
    "dexcom": "continuous glucose monitor",
    "freestyle libre": "continuous glucose monitor",
    "omnipod": "insulin pump",
}

# Lab test name aliases → canonical name
_LAB_ALIASES: dict[str, str] = {
    "hgb": "hemoglobin",
    "hct": "hematocrit",
    "plt": "platelets",
    "wbc": "white blood cell count",
    "rbc": "red blood cell count",
    "bun": "blood urea nitrogen",
    "cr": "creatinine",
    "k+": "potassium",
    "na+": "sodium",
    "cl-": "chloride",
    "co2": "bicarbonate",
    "alt": "alanine aminotransferase",
    "ast": "aspartate aminotransferase",
    "alp": "alkaline phosphatase",
    "tbili": "total bilirubin",
    "ldlc": "ldl cholesterol",
    "hdlc": "hdl cholesterol",
    "trig": "triglycerides",
    "chol": "cholesterol",
    "egfr": "estimated glomerular filtration rate",
    "gfr": "estimated glomerular filtration rate",
    "tsh": "thyroid stimulating hormone",
    "a1c": "hemoglobin a1c",
    "hba1c": "hemoglobin a1c",
}

# Unit normalization: raw → canonical
_UNIT_MAP: dict[str, str] = {
    "mg/dl":  "mg/dL",
    "mg/dl.": "mg/dL",
    "mmol/l": "mmol/L",
    "meq/l":  "mEq/L",
    "u/l":    "U/L",
    "iu/l":   "IU/L",
    "ng/ml":  "ng/mL",
    "pg/ml":  "pg/mL",
    "g/dl":   "g/dL",
    "miu/l":  "mIU/L",
    "ug/dl":  "ug/dL",
    "nmol/l": "nmol/L",
    "umol/l": "umol/L",
    "k/ul":   "K/uL",
    "m/ul":   "M/uL",
    "cells/ul": "cells/uL",
    "percent": "%",
    "pct": "%",
}


def normalize_icd_code(code: str) -> str:
    """
    Normalize an ICD code to uppercase with dot separator.

    Examples:
        E1165  → E11.65
        e11.65 → E11.65
        Z8791  → Z87.91
    """
    code = code.strip().upper()
    # If it has a dot already, just uppercase it
    if "." in code:
        return code
    # Insert dot after the 3rd character if length > 3
    if len(code) > 3:
        return f"{code[:3]}.{code[3:]}"
    return code


def normalize_cpt_code(code: str) -> str:
    """Zero-pad CPT code to 5 digits."""
    code = code.strip()
    if code.isdigit():
        return code.zfill(5)
    return code


def normalize_medication_name(name: str) -> str:
    """Convert trade name to generic name where known; lowercase."""
    lower = name.strip().lower()
    return _TRADE_TO_GENERIC.get(lower, lower)


def normalize_lab_test_name(name: str) -> str:
    """Map lab test abbreviations to canonical names."""
    lower = name.strip().lower()
    return _LAB_ALIASES.get(lower, lower).title()


def normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return unit
    return _UNIT_MAP.get(unit.strip().lower(), unit.strip())


def normalize_date(raw: str | None) -> str | None:
    """
    Parse a free-form date string to ISO 8601 (YYYY-MM-DD).

    Returns None if unparseable.
    """
    if not raw:
        return None
    try:
        parsed = dateutil_parser.parse(raw, fuzzy=True)
        return parsed.strftime("%Y-%m-%d")
    except Exception:
        return raw  # return as-is if parse fails


def normalize_frequency(raw: str | None) -> str | None:
    """Normalize dosing frequency abbreviations."""
    if not raw:
        return None
    mapping = {
        "qd": "once daily",
        "od": "once daily",
        "bid": "twice daily",
        "tid": "three times daily",
        "qid": "four times daily",
        "hs": "at bedtime",
        "ac": "before meals",
        "pc": "after meals",
        "prn": "as needed",
        "qw": "once weekly",
        "biw": "twice weekly",
    }
    lower = raw.strip().lower()
    return mapping.get(lower, raw)
