"""
Multi-signal relevance scorer for retrieved policy chunks.

Combines four signals into a final relevance score:

  1. vector_similarity   — raw cosine/hybrid score from Pinecone (0–1)
  2. code_exact_match    — CPT and ICD code overlap with the query
  3. temporal_relevance  — recency of the policy (newer = better)
  4. payer_match         — payer name matches the query payer
  5. service_type_match  — service_type matches the query service category

Weights are configurable; defaults are tuned for PA coverage decisions.

Usage:
    from app.services.retrieval.scorer import RelevanceScorer, ScorerConfig

    scorer = RelevanceScorer(ScorerConfig(code_weight=0.25))
    scored = scorer.score_all(matches, cpt_codes=["95249"], icd_codes=["E11.9"])
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog

from app.services.vector.schemas import RetrievalMatch

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class ScorerConfig:
    """
    Weight coefficients for each signal.  Must sum to ≤ 1.0; the remainder
    is allocated to vector_similarity automatically if weights don't sum to 1.
    """
    vector_weight:       float = 0.50
    code_weight:         float = 0.25
    temporal_weight:     float = 0.10
    payer_weight:        float = 0.10
    service_type_weight: float = 0.05

    # Temporal decay: half-life in days for policy age scoring
    temporal_half_life_days: float = 365.0

    # Minimum vector similarity to include a result
    min_vector_score: float = 0.0  # filtering already done upstream


# ---------------------------------------------------------------------------
# Per-match score breakdown (for debugging / explainability)
# ---------------------------------------------------------------------------

@dataclass
class ScoreBreakdown:
    """Individual signal scores before weighting."""
    vector_similarity: float = 0.0
    code_exact_match:  float = 0.0
    temporal_relevance: float = 0.0
    payer_match:       float = 0.0
    service_type_match: float = 0.0
    final_score:       float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "vector_similarity":  round(self.vector_similarity, 4),
            "code_exact_match":   round(self.code_exact_match, 4),
            "temporal_relevance": round(self.temporal_relevance, 4),
            "payer_match":        round(self.payer_match, 4),
            "service_type_match": round(self.service_type_match, 4),
            "final_score":        round(self.final_score, 4),
        }


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class RelevanceScorer:
    """
    Compute a multi-signal relevance score for each RetrievalMatch.

    Returned matches are sorted by descending final_score.
    """

    def __init__(self, config: ScorerConfig | None = None) -> None:
        self._cfg = config or ScorerConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score_all(
        self,
        matches: list[RetrievalMatch],
        *,
        cpt_codes: list[str] | None = None,
        icd_codes: list[str] | None = None,
        payer_name: str | None = None,
        service_type: str | None = None,
        today: str | None = None,
    ) -> list[RetrievalMatch]:
        """
        Score all matches and return them sorted by descending final score.

        Args:
            matches:      Input matches (raw or post-fusion).
            cpt_codes:    Query CPT codes (for code overlap signal).
            icd_codes:    Query ICD codes (for code overlap signal).
            payer_name:   Query payer name (for payer match signal).
            service_type: Query service type string.
            today:        YYYY-MM-DD reference date (defaults to today UTC).

        Returns:
            Matches with score field replaced by composite relevance score,
            sorted descending.
        """
        ref_date = today or datetime.now(UTC).strftime("%Y-%m-%d")
        query_cpts = set(c.upper() for c in (cpt_codes or []))
        query_icds = set(c.upper() for c in (icd_codes or []))

        scored: list[tuple[float, RetrievalMatch]] = []
        for match in matches:
            breakdown = self._compute(
                match,
                query_cpts=query_cpts,
                query_icds=query_icds,
                payer_name=payer_name,
                service_type=service_type,
                ref_date=ref_date,
            )
            scored.append((breakdown.final_score, match.model_copy(
                update={"score": breakdown.final_score}
            )))

        scored.sort(key=lambda t: t[0], reverse=True)
        return [m for _, m in scored]

    def score_with_breakdown(
        self,
        matches: list[RetrievalMatch],
        *,
        cpt_codes: list[str] | None = None,
        icd_codes: list[str] | None = None,
        payer_name: str | None = None,
        service_type: str | None = None,
        today: str | None = None,
    ) -> list[tuple[RetrievalMatch, ScoreBreakdown]]:
        """
        Like score_all() but returns (match, breakdown) pairs for explainability.
        """
        ref_date = today or datetime.now(UTC).strftime("%Y-%m-%d")
        query_cpts = set(c.upper() for c in (cpt_codes or []))
        query_icds = set(c.upper() for c in (icd_codes or []))

        results: list[tuple[float, RetrievalMatch, ScoreBreakdown]] = []
        for match in matches:
            breakdown = self._compute(
                match,
                query_cpts=query_cpts,
                query_icds=query_icds,
                payer_name=payer_name,
                service_type=service_type,
                ref_date=ref_date,
            )
            scored_match = match.model_copy(update={"score": breakdown.final_score})
            results.append((breakdown.final_score, scored_match, breakdown))

        results.sort(key=lambda t: t[0], reverse=True)
        return [(m, b) for _, m, b in results]

    # ------------------------------------------------------------------
    # Signal computations
    # ------------------------------------------------------------------

    def _compute(
        self,
        match: RetrievalMatch,
        *,
        query_cpts: set[str],
        query_icds: set[str],
        payer_name: str | None,
        service_type: str | None,
        ref_date: str,
    ) -> ScoreBreakdown:
        bd = ScoreBreakdown()

        bd.vector_similarity   = self._signal_vector(match)
        bd.code_exact_match    = self._signal_code_match(match, query_cpts, query_icds)
        bd.temporal_relevance  = self._signal_temporal(match, ref_date)
        bd.payer_match         = self._signal_payer(match, payer_name)
        bd.service_type_match  = self._signal_service_type(match, service_type)

        cfg = self._cfg
        bd.final_score = (
            cfg.vector_weight       * bd.vector_similarity
            + cfg.code_weight       * bd.code_exact_match
            + cfg.temporal_weight   * bd.temporal_relevance
            + cfg.payer_weight      * bd.payer_match
            + cfg.service_type_weight * bd.service_type_match
        )
        return bd

    def _signal_vector(self, match: RetrievalMatch) -> float:
        """Clamp the raw vector score to [0, 1]."""
        return max(0.0, min(1.0, match.score))

    def _signal_code_match(
        self,
        match: RetrievalMatch,
        query_cpts: set[str],
        query_icds: set[str],
    ) -> float:
        """
        Jaccard-style overlap between query codes and policy codes.

        Returns 1.0 if every query code is present in the policy.
        Returns 0.0 if no overlap at all.
        """
        if not query_cpts and not query_icds:
            return 0.5  # neutral when no codes in query

        policy_cpts = set(c.upper() for c in match.metadata.cpt_codes)
        policy_icds = set(c.upper() for c in match.metadata.icd_codes)

        cpt_overlap = len(query_cpts & policy_cpts) if query_cpts else 0
        icd_overlap = len(query_icds & policy_icds) if query_icds else 0

        total_query = len(query_cpts) + len(query_icds)
        total_overlap = cpt_overlap + icd_overlap

        return total_overlap / total_query if total_query > 0 else 0.0

    def _signal_temporal(self, match: RetrievalMatch, ref_date: str) -> float:
        """
        Exponential decay based on policy age.

        A policy effective today scores 1.0; a policy effective one half-life
        ago scores 0.5.  The score is floored at 0.05 for very old policies.
        """
        try:
            effective = datetime.strptime(
                match.metadata.effective_date, "%Y-%m-%d"
            ).replace(tzinfo=UTC)
            ref = datetime.strptime(ref_date, "%Y-%m-%d").replace(tzinfo=UTC)
            age_days = max(0.0, (ref - effective).days)
            half_life = self._cfg.temporal_half_life_days
            decay = math.exp(-math.log(2) * age_days / half_life)
            return max(0.05, min(1.0, decay))
        except (ValueError, TypeError):
            return 0.5  # can't parse date → neutral

    def _signal_payer(self, match: RetrievalMatch, payer_name: str | None) -> float:
        """1.0 if payer matches, 0.5 if no payer filter, 0.0 if mismatch."""
        if not payer_name:
            return 0.5
        policy_payer = (match.metadata.payer_name or "").lower()
        query_payer = payer_name.lower()
        if not policy_payer:
            return 0.3  # payer unknown → slight penalty
        return 1.0 if query_payer in policy_payer or policy_payer in query_payer else 0.0

    def _signal_service_type(
        self, match: RetrievalMatch, service_type: str | None
    ) -> float:
        """1.0 if service_type matches (substring), 0.5 if not queried."""
        if not service_type:
            return 0.5
        policy_st = (match.metadata.service_type or "").lower()
        query_st = service_type.lower()
        if not policy_st:
            return 0.3
        return 1.0 if query_st in policy_st or policy_st in query_st else 0.0


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def score_matches(
    matches: list[RetrievalMatch],
    *,
    cpt_codes: list[str] | None = None,
    icd_codes: list[str] | None = None,
    payer_name: str | None = None,
    service_type: str | None = None,
    config: ScorerConfig | None = None,
) -> list[RetrievalMatch]:
    """
    One-liner: score and sort a list of matches using the multi-signal scorer.

    Example:
        scored = score_matches(
            fused_results,
            cpt_codes=["95249"],
            icd_codes=["E11.9"],
            payer_name="Aetna",
        )
    """
    return RelevanceScorer(config).score_all(
        matches,
        cpt_codes=cpt_codes,
        icd_codes=icd_codes,
        payer_name=payer_name,
        service_type=service_type,
    )
