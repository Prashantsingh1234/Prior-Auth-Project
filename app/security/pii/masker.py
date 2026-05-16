"""
PHI / PII masking service.

PIIMasker applies HIPAA Safe Harbor masking to free-text strings,
structured dicts, and log records.  It is used in two contexts:

  1. Output sanitization (post-LLM): mask PHI before API responses
  2. Log sanitization: strip PHI from structlog event dicts
  3. Document ingestion: mask PHI in extracted text before indexing

Usage:
    masker = PIIMasker()

    # Mask a free-text string
    clean = masker.mask(text)

    # Mask specific dict fields
    clean_record = masker.mask_dict(record, fields=["notes", "summary"])

    # Check if text contains PHI (without modifying)
    has_phi, entities = masker.detect(text)

    # Structlog processor (add to structlog chain)
    structlog.configure(processors=[masker.as_structlog_processor(), ...])
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.security.pii.patterns import HIPAA_MASK_PATTERNS, MaskPattern

logger = structlog.get_logger(__name__)


@dataclass
class MaskResult:
    """Result of a masking operation."""
    original_length: int
    masked_text:     str
    entities_masked: int
    entity_types:    list[str] = field(default_factory=list)
    was_modified:    bool = False


class PIIMasker:
    """
    HIPAA-compliant PHI/PII masking service.

    Thread-safe: stateless (no mutable state after construction).
    """

    def __init__(
        self,
        patterns: list[MaskPattern] | None = None,
        log_detections: bool = True,
    ) -> None:
        self._patterns      = patterns or HIPAA_MASK_PATTERNS
        self._log_detections = log_detections

    # ------------------------------------------------------------------
    # Core masking
    # ------------------------------------------------------------------

    def mask(self, text: str) -> str:
        """
        Apply all PHI masking patterns to ``text`` and return the cleaned string.

        Patterns are applied in priority order.  Once a span is masked,
        it is not re-processed by lower-priority patterns.
        """
        if not text:
            return text

        result = text
        for mp in self._patterns:
            if mp.transformer is not None:
                result = mp.pattern.sub(mp.transformer, result)
            else:
                result = mp.pattern.sub(mp.mask, result)

        return result

    def mask_detailed(self, text: str) -> MaskResult:
        """
        Apply masking and return a MaskResult with entity statistics.

        Use this when you need to know *what* was masked (for audit logging).
        """
        if not text:
            return MaskResult(
                original_length=0, masked_text="", entities_masked=0
            )

        result = text
        entities_masked = 0
        entity_types_found: list[str] = []

        for mp in self._patterns:
            if mp.transformer is not None:
                new_result, n = mp.pattern.subn(mp.transformer, result)
            else:
                new_result, n = mp.pattern.subn(mp.mask, result)
            if n > 0:
                entities_masked += n
                entity_types_found.extend([mp.name] * n)
            result = new_result

        was_modified = result != text

        if was_modified and self._log_detections:
            logger.warning(
                "pii_masker.phi_masked",
                entity_count=entities_masked,
                entity_types=list(set(entity_types_found))[:8],
                original_length=len(text),
                masked_length=len(result),
            )

        return MaskResult(
            original_length=len(text),
            masked_text=result,
            entities_masked=entities_masked,
            entity_types=list(set(entity_types_found)),
            was_modified=was_modified,
        )

    # ------------------------------------------------------------------
    # Detection only (no modification)
    # ------------------------------------------------------------------

    def detect(self, text: str) -> tuple[bool, list[str]]:
        """
        Check if ``text`` contains PHI without modifying it.

        Returns (has_phi, list_of_entity_type_names).
        """
        if not text:
            return False, []

        found_types: list[str] = []
        for mp in self._patterns:
            if mp.pattern.search(text):
                found_types.append(mp.name)

        return bool(found_types), found_types

    # ------------------------------------------------------------------
    # Dict masking
    # ------------------------------------------------------------------

    def mask_dict(
        self,
        data: dict[str, Any],
        fields: list[str],
    ) -> dict[str, Any]:
        """
        Mask PHI in specified string fields of a dict.

        Returns a new dict (original is not mutated).
        """
        result = dict(data)
        for key in fields:
            val = result.get(key)
            if isinstance(val, str):
                result[key] = self.mask(val)
            elif isinstance(val, list):
                result[key] = [self.mask(item) if isinstance(item, str) else item for item in val]
        return result

    def mask_all_strings(self, data: dict[str, Any], depth: int = 0) -> dict[str, Any]:
        """Recursively mask all string values in a nested dict (max depth 5)."""
        if depth > 5:
            return data
        result = {}
        for k, v in data.items():
            if isinstance(v, str):
                result[k] = self.mask(v)
            elif isinstance(v, dict):
                result[k] = self.mask_all_strings(v, depth + 1)
            elif isinstance(v, list):
                result[k] = [
                    self.mask(item) if isinstance(item, str)
                    else (self.mask_all_strings(item, depth + 1) if isinstance(item, dict) else item)
                    for item in v
                ]
            else:
                result[k] = v
        return result

    # ------------------------------------------------------------------
    # Structlog processor
    # ------------------------------------------------------------------

    def as_structlog_processor(self):
        """
        Return a structlog processor that masks PHI in log event dicts.

        Usage:
            structlog.configure(processors=[
                masker.as_structlog_processor(),
                ...
            ])
        """
        _phi_fields = frozenset({
            "member_id", "patient_id", "ssn", "dob", "mrn", "npi",
            "email", "phone", "address", "name", "notes", "summary",
            "message", "error", "prompt", "output", "content",
        })

        def _processor(logger, method, event_dict: dict[str, Any]) -> dict[str, Any]:
            for key in list(event_dict.keys()):
                if key in _phi_fields and isinstance(event_dict[key], str):
                    event_dict[key] = self.mask(event_dict[key])
            return event_dict

        return _processor


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_masker: PIIMasker | None = None


def get_pii_masker() -> PIIMasker:
    global _masker
    if _masker is None:
        _masker = PIIMasker()
    return _masker
