"""
Medical code validators — ICD and CPT.

ICD validation:  WHO ICD-11 API (async, with cache)
CPT validation:  Regex rules + category lookup (no external dependency)

Both validators return ValidationStatus and populate api_description
when a live API response is available.
"""

from __future__ import annotations

import re

import structlog

from app.services.extraction.icd_client import ICDApiClient
from app.services.extraction.models import (
    CodeSystem,
    ValidatedCode,
    ValidationStatus,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# ICD patterns
# ---------------------------------------------------------------------------

# ICD-10-CM: letter + 2 digits, optional dot + up to 4 alphanumeric chars
_ICD10_RE = re.compile(r"^[A-TV-Z]\d{2}(?:\.\d{1,4})?$", re.IGNORECASE)

# ICD-11 MMS codes (X-coded format used by WHO): varies by chapter
_ICD11_RE = re.compile(r"^[A-Z]{1,2}\d{2,5}(?:\.[A-Z0-9]{1,6})?$", re.IGNORECASE)

# ---------------------------------------------------------------------------
# CPT category lookup
# ---------------------------------------------------------------------------

_CPT_CATEGORIES: list[tuple[range, str]] = [
    (range(99_000, 100_000), "Evaluation & Management"),
    (range(10_000,  70_000), "Surgery"),
    (range(70_000,  80_000), "Radiology"),
    (range(80_000,  90_000), "Pathology & Laboratory"),
    (range(90_000,  99_000), "Medicine"),
    (range(0_001,   1_000),  "Anesthesia"),
]


def _cpt_category(code_str: str) -> str | None:
    try:
        code_int = int(code_str)
    except ValueError:
        return None
    for code_range, category in _CPT_CATEGORIES:
        if code_int in code_range:
            return category
    return "Other"


# ---------------------------------------------------------------------------
# ICD Validator
# ---------------------------------------------------------------------------

class ICDValidator:
    """
    Validates ICD codes against the WHO ICD-11 API.

    Falls back to regex format check when the API is unavailable.

    Usage:
        validator = ICDValidator(icd_client)
        codes = await validator.validate_batch(["E11.65", "Z87.891"])
    """

    def __init__(self, client: ICDApiClient) -> None:
        self._client = client
        self._log    = structlog.get_logger(self.__class__.__name__)

    async def validate_batch(
        self,
        codes: list[str],
        code_system: CodeSystem = CodeSystem.ICD_10_CM,
    ) -> list[ValidatedCode]:
        results: list[ValidatedCode] = []
        for code in codes:
            result = await self.validate_one(code, code_system)
            results.append(result)
        return results

    async def validate_one(
        self,
        code: str,
        code_system: CodeSystem = CodeSystem.ICD_10_CM,
    ) -> ValidatedCode:
        code = code.strip().upper()

        # Format check first
        if not self._is_valid_format(code):
            return ValidatedCode(
                code=code,
                code_system=code_system,
                validation_status=ValidationStatus.INVALID,
            )

        # Try WHO ICD-11 API
        try:
            info = await self._client.validate_code(code)
            if info is None:
                status = ValidationStatus.UNVERIFIED
                description = None
            elif info.is_valid:
                status = ValidationStatus.VALID
                description = info.description
            else:
                status = ValidationStatus.NOT_FOUND
                description = None
        except Exception as err:
            self._log.warning("icd_validator.api_error", code=code, error=str(err))
            # Degrade to format-only check
            status = ValidationStatus.UNVERIFIED
            description = None

        return ValidatedCode(
            code=code,
            code_system=code_system,
            validation_status=status,
            api_description=description,
        )

    @staticmethod
    def _is_valid_format(code: str) -> bool:
        return bool(_ICD10_RE.match(code) or _ICD11_RE.match(code))


# ---------------------------------------------------------------------------
# CPT Validator
# ---------------------------------------------------------------------------

class CPTValidator:
    """
    Validates CPT codes using format rules and category mapping.

    No external API required — CPT is defined by AMA and requires
    a commercial license for the full database. We validate format
    and provide category labels from the known range mapping.
    """

    def __init__(self) -> None:
        self._log = structlog.get_logger(self.__class__.__name__)

    def validate_batch(self, codes: list[str]) -> list[ValidatedCode]:
        return [self.validate_one(c) for c in codes]

    def validate_one(self, code: str) -> ValidatedCode:
        code = code.strip()

        if not self._is_valid_format(code):
            return ValidatedCode(
                code=code,
                code_system=CodeSystem.CPT_4,
                validation_status=ValidationStatus.INVALID,
            )

        category = _cpt_category(code)
        return ValidatedCode(
            code=code,
            description=category,
            code_system=CodeSystem.CPT_4,
            validation_status=ValidationStatus.VALID,
            api_description=category,
        )

    @staticmethod
    def _is_valid_format(code: str) -> bool:
        """CPT: exactly 5 digits, or 5 digits + single letter (Category III)."""
        return bool(re.match(r"^\d{5}[A-Z]?$", code))
