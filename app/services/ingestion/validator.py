"""
Chunk validation stage of the policy ingestion pipeline.

Runs rule-based checks on each PolicyCriterion before it reaches Pinecone.
A chunk that fails any hard rule is quarantined in invalid_criteria — it is
logged but NOT uploaded.  A chunk that triggers only soft rules is marked
with a reduced confidence score and a warning, but still goes through.

Hard rules (invalid):
  - Text shorter than MIN_TEXT_LENGTH
  - Text appears to be a page header / footer (repeated short phrase)
  - Text is entirely numeric or whitespace
  - Text contains no alphabetic characters

Soft rules (warning only):
  - Text is very short (< WARN_TEXT_LENGTH but ≥ MIN_TEXT_LENGTH)
  - Confidence < MIN_CONFIDENCE
  - No section_header present (reduces retrieval context)
"""

from __future__ import annotations

import re
import structlog

from app.services.ingestion.models import (
    BatchValidationResult,
    PolicyCriterion,
    ValidationResult,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

MIN_TEXT_LENGTH  = 20   # Hard lower bound — matches PolicyCriterion.text min_length
WARN_TEXT_LENGTH = 60   # Chunks below this get a soft warning
MIN_CONFIDENCE   = 0.5  # Chunks with confidence below this get a warning

# Heuristics for header/footer detection
_HEADER_FOOTER_RE = re.compile(
    r"^(?:page\s+\d+|confidential|proprietary|internal use only|"
    r"©\s*\d{4}|all rights reserved|\d+\s*of\s*\d+|continued\.{0,3})$",
    re.IGNORECASE,
)

# "Garbage" lines — typically OCR artifacts or table row fragments
_GARBAGE_RE = re.compile(r"^[\W\d_]{1,15}$")


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class ChunkValidator:
    """
    Validates a list of PolicyCriterion objects.

    Usage:
        validator = ChunkValidator()
        result = validator.validate_batch(criteria)
    """

    def __init__(self) -> None:
        self._log = structlog.get_logger(self.__class__.__name__)

    def validate_batch(
        self, criteria: list[PolicyCriterion]
    ) -> BatchValidationResult:
        """Validate every criterion; partition into valid / invalid."""
        valid:   list[PolicyCriterion] = []
        invalid: list[PolicyCriterion] = []
        results: list[ValidationResult] = []

        for criterion in criteria:
            vr = self._validate_one(criterion)
            results.append(vr)

            if vr.is_valid:
                valid.append(criterion)
            else:
                invalid.append(criterion)
                self._log.warning(
                    "validator.chunk_invalid",
                    chunk_index=criterion.chunk_index,
                    errors=vr.errors,
                    text_preview=criterion.text[:80],
                )

        pass_rate = len(valid) / len(criteria) if criteria else 0.0
        self._log.info(
            "validator.complete",
            total=len(criteria),
            valid=len(valid),
            invalid=len(invalid),
            pass_rate=round(pass_rate, 3),
        )

        return BatchValidationResult(
            valid_criteria=valid,
            invalid_criteria=invalid,
            results=results,
        )

    # ------------------------------------------------------------------

    def _validate_one(self, criterion: PolicyCriterion) -> ValidationResult:
        errors:   list[str] = []
        warnings: list[str] = []
        text = criterion.text.strip()

        # --- Hard rules ---

        if len(text) < MIN_TEXT_LENGTH:
            errors.append(
                f"Text too short ({len(text)} chars, minimum {MIN_TEXT_LENGTH})"
            )

        if not any(c.isalpha() for c in text):
            errors.append("Text contains no alphabetic characters")

        if _HEADER_FOOTER_RE.match(text):
            errors.append("Text matches header/footer pattern")

        if _GARBAGE_RE.match(text):
            errors.append("Text appears to be an OCR artifact")

        # --- Soft rules (warnings only) ---

        if not errors:
            if len(text) < WARN_TEXT_LENGTH:
                warnings.append(
                    f"Short chunk ({len(text)} chars) — may lack retrieval context"
                )

            if criterion.confidence < MIN_CONFIDENCE:
                warnings.append(
                    f"Low confidence ({criterion.confidence:.2f})"
                )

            if criterion.section_header is None:
                warnings.append(
                    "No section_header — retrieval context will be weaker"
                )

        return ValidationResult(
            chunk_index=criterion.chunk_index,
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
