"""
Multi-signal confidence scoring system for extracted medical entities.

Signals used (weights sum to 1.0):
  regex_found    0.20  — entity was found by the deterministic regex parser
  llm_found      0.25  — entity was returned by the LLM
  api_validated  0.30  — ICD/CPT code confirmed valid by external API
  grounded       0.15  — entity text appears verbatim in the source document
  consensus      0.10  — both regex and LLM returned the same entity

For entities that cannot be API-validated (symptoms, demographics, etc.)
the api_validated weight is redistributed proportionally to the other signals.
"""

from __future__ import annotations

from typing import TypeVar

from app.services.extraction.models import ConfidenceSignals, ValidationStatus

# Base signal weights
_W_REGEX     = 0.20
_W_LLM       = 0.25
_W_API       = 0.30
_W_GROUNDED  = 0.15
_W_CONSENSUS = 0.10

# When API validation is not applicable, redistribute its weight
_REDISTRIBUTION = {
    "regex":     _W_REGEX     / (1.0 - _W_API),
    "llm":       _W_LLM       / (1.0 - _W_API),
    "grounded":  _W_GROUNDED  / (1.0 - _W_API),
    "consensus": _W_CONSENSUS / (1.0 - _W_API),
}

# Penalize when grounding check fails (entity not found in source)
_GROUNDING_PENALTY = 0.40


class ConfidenceScorer:
    """
    Computes final confidence scores for extracted entities.

    Usage:
        scorer = ConfidenceScorer()
        scorer.score(signals, api_applicable=True)
        # → mutates signals.final_score in-place
    """

    def score(
        self,
        signals: ConfidenceSignals,
        api_applicable: bool = False,
    ) -> float:
        """
        Compute and store the final confidence score.

        Args:
            signals:        Signal flags from the extraction process
            api_applicable: True for ICD/CPT codes that can be API-validated

        Returns:
            Final confidence score in [0.0, 1.0].
        """
        if api_applicable:
            score = (
                (_W_REGEX     * signals.regex_found)
                + (_W_LLM       * signals.llm_found)
                + (_W_API       * signals.api_validated)
                + (_W_GROUNDED  * signals.grounded)
                + (_W_CONSENSUS * signals.consensus)
            )
        else:
            r = _REDISTRIBUTION
            score = (
                (r["regex"]     * signals.regex_found)
                + (r["llm"]       * signals.llm_found)
                + (r["grounded"]  * signals.grounded)
                + (r["consensus"] * signals.consensus)
            )

        # Penalize if grounding failed (entity cannot be found in source)
        if not signals.grounded and (signals.regex_found or signals.llm_found):
            score *= (1.0 - _GROUNDING_PENALTY)

        signals.final_score = round(min(max(score, 0.0), 1.0), 4)
        return signals.final_score

    def score_from_validation(
        self,
        signals: ConfidenceSignals,
        validation_status: ValidationStatus,
    ) -> float:
        """
        Convenience method that sets api_validated from a ValidationStatus.
        """
        signals.api_validated = validation_status == ValidationStatus.VALID
        return self.score(signals, api_applicable=True)

    def compute_overall(self, scores: list[float]) -> float:
        """
        Compute document-level overall confidence from all entity scores.

        Uses a weighted mean that penalizes outlier low-confidence entities.
        """
        if not scores:
            return 0.0
        valid = [s for s in scores if s > 0.0]
        if not valid:
            return 0.0
        avg = sum(valid) / len(valid)
        # Penalty for the fraction of zero-confidence entities
        zero_ratio = 1.0 - len(valid) / len(scores)
        return round(avg * (1.0 - 0.2 * zero_ratio), 4)


def ground_check(entity_text: str, source_text: str) -> bool:
    """
    Return True if entity_text (or a substring) appears in source_text.

    Normalizes whitespace and case for comparison.
    """
    if not entity_text or not source_text:
        return False
    needle   = " ".join(entity_text.lower().split())
    haystack = " ".join(source_text.lower().split())
    # Accept partial match for long entity names
    if len(needle) > 20:
        needle = needle[:20]
    return needle in haystack
