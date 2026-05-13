"""
Metadata extraction stage of the policy ingestion pipeline.

Extracts from policy document text:
  - CPT codes (5-digit numeric)
  - ICD-10-CM codes (letter + 2 digits, optional decimal subdivision)
  - Policy version string
  - Effective date
  - Expiration / review date
  - Payer name
  - Service type
  - Revision history entries

All fields are optional — the extractor returns what it can find and leaves
the rest as None.  Calling code merges extracted metadata with caller-supplied
metadata from PolicyIngestionRequest (caller values take precedence).
"""

from __future__ import annotations

import re
import structlog
from datetime import date
from typing import Sequence

from dateutil import parser as dateutil_parser

from app.services.ingestion.models import ExtractedMetadata, PolicyIngestionRequest

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# CPT: exactly 5 digits, word boundaries, not followed by more digits or "."
_CPT_RE = re.compile(r"\b(\d{5})\b(?!\d|\.)")

# CPT ranges: e.g. "CPT 99201-99205"
_CPT_RANGE_RE = re.compile(r"\bCPT[:\s]+(\d{5})\s*[-–—]\s*(\d{5})\b", re.IGNORECASE)

# ICD-10-CM: letter + 2 digits, optional dot + 1–4 alphanumeric
_ICD_RE = re.compile(r"\b([A-TV-Z]\d{2}(?:\.\d{1,4})?)\b")

# Version strings: "Version 3", "v3.1", "Rev 2", "Revision 2024-01"
_VERSION_RE = re.compile(
    r"(?:version|ver\.?|v|revision|rev\.?)[:\s]+([0-9]+(?:\.[0-9]+)*(?:[A-Za-z]\w*)?)",
    re.IGNORECASE,
)

# Date labels
_DATE_LABEL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"effective\s+date[:\s]+([^\n]{5,40})", re.I), "effective"),
    (re.compile(r"effective[:\s]+([^\n]{5,40})", re.I), "effective"),
    (re.compile(r"date\s+effective[:\s]+([^\n]{5,40})", re.I), "effective"),
    (re.compile(r"(?:expir|review|sunset|end|through)\s+date[:\s]+([^\n]{5,40})", re.I), "expiration"),
    (re.compile(r"next\s+review[:\s]+([^\n]{5,40})", re.I), "expiration"),
    (re.compile(r"policy\s+date[:\s]+([^\n]{5,40})", re.I), "effective"),
]

# Payer name — look for common payer identifiers near page top
_PAYER_CANDIDATES = [
    "Aetna", "Anthem", "Blue Cross", "BlueCross", "BCBS", "Cigna", "Humana",
    "Molina", "United", "UnitedHealth", "UHC", "Centene", "WellCare", "Magellan",
    "Amerigroup", "Caresource", "GEHA", "TriCare", "Tricare", "Kaiser",
    "Medicare", "Medicaid",
]
_PAYER_RE = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in _PAYER_CANDIDATES) + r")\b",
    re.IGNORECASE,
)

# Service type — look for the procedure/service being reviewed
_SERVICE_RE = re.compile(
    r"(?:policy\s+for|coverage\s+for|criteria\s+for|regarding|subject:\s*)"
    r"([A-Z][^\n]{5,80})",
    re.IGNORECASE,
)

# Revision history line: e.g. "01/2023 – Policy created", "Rev. 2024-06: Updated criteria"
_REVISION_LINE_RE = re.compile(
    r"(?:^|\n)\s*"
    r"((?:\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4})[^\n]{5,120})",
)


# ---------------------------------------------------------------------------
# Public extractor
# ---------------------------------------------------------------------------

class MetadataExtractor:
    """
    Extracts structured metadata from policy document text.

    Usage:
        extractor = MetadataExtractor()
        metadata = extractor.extract(full_text)

    After extraction, merge with caller-supplied request fields:
        merged = extractor.merge(request, metadata)
    """

    def __init__(self) -> None:
        self._log = structlog.get_logger(self.__class__.__name__)

    def extract(self, text: str) -> ExtractedMetadata:
        """Run all extractors and return an ExtractedMetadata."""
        cpt_codes  = self._extract_cpt(text)
        icd_codes  = self._extract_icd(text)
        version    = self._extract_version(text)
        eff_date, exp_date = self._extract_dates(text)
        payer      = self._extract_payer(text)
        service    = self._extract_service_type(text)
        revisions  = self._extract_revision_history(text)

        self._log.info(
            "extractor.complete",
            cpt_count=len(cpt_codes),
            icd_count=len(icd_codes),
            version=version,
            effective_date=eff_date,
            payer=payer,
        )

        return ExtractedMetadata(
            cpt_codes=cpt_codes,
            icd_codes=icd_codes,
            policy_version=version,
            effective_date=eff_date,
            expiration_date=exp_date,
            payer_name=payer,
            service_type=service,
            revision_history=revisions,
        )

    @staticmethod
    def merge(
        request: PolicyIngestionRequest,
        extracted: ExtractedMetadata,
    ) -> PolicyIngestionRequest:
        """
        Merge extracted metadata into a request, caller values taking precedence.

        Fields present on the request are kept as-is; absent fields are filled
        from the extraction result.
        """
        updates: dict[str, object] = {}

        if not request.payer_name and extracted.payer_name:
            updates["payer_name"] = extracted.payer_name
        if not request.service_type and extracted.service_type:
            updates["service_type"] = extracted.service_type
        if not request.policy_version and extracted.policy_version:
            updates["policy_version"] = extracted.policy_version
        if not request.effective_date and extracted.effective_date:
            updates["effective_date"] = extracted.effective_date
        if not request.expiration_date and extracted.expiration_date:
            updates["expiration_date"] = extracted.expiration_date

        # Merge code lists, dedup, preserve caller ordering first
        merged_cpt = _merge_codes(request.cpt_codes, extracted.cpt_codes)
        merged_icd = _merge_codes(request.icd_codes, extracted.icd_codes)
        if merged_cpt != request.cpt_codes:
            updates["cpt_codes"] = merged_cpt
        if merged_icd != request.icd_codes:
            updates["icd_codes"] = merged_icd

        if updates:
            return request.model_copy(update=updates)
        return request

    # ------------------------------------------------------------------
    # Individual extractors
    # ------------------------------------------------------------------

    def _extract_cpt(self, text: str) -> list[str]:
        codes: list[str] = []

        # Explicit ranges first
        for m in _CPT_RANGE_RE.finditer(text):
            start, end = int(m.group(1)), int(m.group(2))
            if end - start <= 50:  # sanity: don't expand huge ranges
                codes.extend(str(c) for c in range(start, end + 1))

        # Individual codes
        codes.extend(_CPT_RE.findall(text))

        return _dedup(codes)

    @staticmethod
    def _extract_icd(text: str) -> list[str]:
        raw = _ICD_RE.findall(text)
        # Filter out false positives: version identifiers like "v2.1" already stripped,
        # but single letters followed by digits that look like ICD but are page refs
        codes = [c for c in raw if not c.startswith(("U0", "U07", "U08", "U09")) or True]
        return _dedup(codes)

    @staticmethod
    def _extract_version(text: str) -> str | None:
        m = _VERSION_RE.search(text)
        return m.group(1) if m else None

    @staticmethod
    def _extract_dates(text: str) -> tuple[str | None, str | None]:
        eff_date: str | None = None
        exp_date: str | None = None

        for pattern, kind in _DATE_LABEL_PATTERNS:
            m = pattern.search(text)
            if not m:
                continue
            raw = m.group(1).strip().rstrip(",.;")
            parsed = _safe_parse_date(raw)
            if parsed is None:
                continue
            formatted = parsed.strftime("%Y-%m-%d")
            if kind == "effective" and eff_date is None:
                eff_date = formatted
            elif kind == "expiration" and exp_date is None:
                exp_date = formatted

        return eff_date, exp_date

    @staticmethod
    def _extract_payer(text: str) -> str | None:
        # Search only the first 2000 characters (header area)
        m = _PAYER_RE.search(text[:2_000])
        return m.group(1).title() if m else None

    @staticmethod
    def _extract_service_type(text: str) -> str | None:
        m = _SERVICE_RE.search(text[:3_000])
        if m:
            service = m.group(1).strip().rstrip(".,;:")
            # Truncate at first newline or sentence boundary
            service = re.split(r"[.\n]", service)[0].strip()
            if 5 < len(service) < 150:
                return service
        return None

    @staticmethod
    def _extract_revision_history(text: str) -> list[str]:
        matches = _REVISION_LINE_RE.findall(text)
        return [m.strip() for m in matches if len(m.strip()) > 10][:20]


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _dedup(codes: Sequence[str]) -> list[str]:
    seen: dict[str, None] = {}
    for c in codes:
        seen[c] = None
    return list(seen.keys())


def _merge_codes(primary: list[str], secondary: list[str]) -> list[str]:
    combined = list(primary)
    for code in secondary:
        if code not in combined:
            combined.append(code)
    return combined


def _safe_parse_date(raw: str) -> date | None:
    """Parse a date string, returning None if unparseable."""
    try:
        return dateutil_parser.parse(raw, fuzzy=True).date()
    except Exception:
        return None
