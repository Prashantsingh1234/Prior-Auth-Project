"""
Reciprocal Rank Fusion (RRF) and score normalization utilities.

RRF merges multiple ranked result lists into a single ranked list without
requiring calibrated scores across systems.  The formula:

    RRF(d) = Σ  1 / (k + rank_i(d))
             i

where k=60 is the standard smoothing constant (Cormack et al., 2009).

Score normalization (min-max) is applied *before* fusion so that raw
Pinecone similarity scores (0.5–1.0 range) do not dominate BM25 or
code-match contributions whose native ranges differ.

Usage:
    from app.services.retrieval.fusion import RRFFusion, normalize_scores

    fused = RRFFusion(k=60).fuse([semantic_matches, bm25_matches, cpt_matches])
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import structlog

from app.services.vector.schemas import RetrievalMatch

logger = structlog.get_logger(__name__)

# Standard RRF smoothing constant
DEFAULT_K = 60

# Epsilon to avoid division by zero during normalization
_EPS = 1e-9


# ---------------------------------------------------------------------------
# Score normalization
# ---------------------------------------------------------------------------

def normalize_scores(matches: list[RetrievalMatch]) -> list[RetrievalMatch]:
    """
    Apply min-max normalization to similarity scores in-place (returns new list).

    Maps [min_score, max_score] → [0.0, 1.0] per result set so that
    different retrieval systems contribute equally to downstream fusion.
    """
    if not matches:
        return []

    scores = [m.score for m in matches]
    lo, hi = min(scores), max(scores)
    span = hi - lo + _EPS

    return [
        m.model_copy(update={"score": (m.score - lo) / span})
        for m in matches
    ]


def softmax_scores(matches: list[RetrievalMatch], temperature: float = 1.0) -> list[RetrievalMatch]:
    """
    Softmax normalization — useful when score differences should be amplified.

    temperature < 1.0 → sharper distribution (higher scores get more weight)
    temperature > 1.0 → flatter distribution (scores become more uniform)
    """
    if not matches:
        return []

    scaled = [m.score / temperature for m in matches]
    max_s = max(scaled)
    exps = [math.exp(s - max_s) for s in scaled]
    total = sum(exps) + _EPS

    return [
        m.model_copy(update={"score": e / total})
        for m, e in zip(matches, exps)
    ]


# ---------------------------------------------------------------------------
# RRF fusion
# ---------------------------------------------------------------------------

@dataclass
class FusedMatch:
    """A match after RRF fusion, carrying provenance from contributing lists."""
    vector_id: str
    rrf_score: float
    match: RetrievalMatch
    source_ranks: dict[str, int] = field(default_factory=dict)
    source_scores: dict[str, float] = field(default_factory=dict)


class RRFFusion:
    """
    Reciprocal Rank Fusion over multiple RetrievalMatch lists.

    Each list is treated as an independent ranking; RRF computes a combined
    score that rewards documents appearing consistently near the top of
    multiple lists.

    Args:
        k:           Smoothing constant (default 60)
        weights:     Per-list weight multiplier; same length as input lists.
                     Defaults to uniform (1.0 for each list).
        min_lists:   Minimum number of lists a document must appear in to be
                     included in results (default 1 — include all).
    """

    def __init__(
        self,
        k: int = DEFAULT_K,
        weights: list[float] | None = None,
        min_lists: int = 1,
    ) -> None:
        self._k = k
        self._weights = weights
        self._min_lists = min_lists

    def fuse(
        self,
        ranked_lists: Sequence[list[RetrievalMatch]],
        list_names: list[str] | None = None,
    ) -> list[RetrievalMatch]:
        """
        Fuse multiple ranked lists into a single ranked list.

        Args:
            ranked_lists:  Each element is a list of RetrievalMatch objects
                           sorted by descending score.  The list position IS
                           the rank (position 0 = rank 1).
            list_names:    Optional human-readable names for provenance logging.

        Returns:
            A new list of RetrievalMatch objects sorted by descending RRF score.
            The score field is the RRF score (not comparable to raw similarity).
        """
        if not ranked_lists:
            return []

        n_lists = len(ranked_lists)
        names = list_names or [f"list_{i}" for i in range(n_lists)]
        weights = self._weights or [1.0] * n_lists

        if len(weights) != n_lists:
            logger.warning(
                "rrf.weight_mismatch",
                weights_len=len(weights),
                lists_len=n_lists,
            )
            weights = [1.0] * n_lists

        # doc_id → FusedMatch accumulator
        accumulated: dict[str, FusedMatch] = {}

        for list_idx, (matches, name, weight) in enumerate(
            zip(ranked_lists, names, weights)
        ):
            for rank_0based, match in enumerate(matches):
                rank = rank_0based + 1  # 1-based
                rrf_contrib = weight / (self._k + rank)
                vid = match.vector_id

                if vid not in accumulated:
                    accumulated[vid] = FusedMatch(
                        vector_id=vid,
                        rrf_score=0.0,
                        match=match,
                    )

                accumulated[vid].rrf_score += rrf_contrib
                accumulated[vid].source_ranks[name] = rank
                accumulated[vid].source_scores[name] = match.score

        # Apply min_lists filter
        qualifying = {
            vid: fm
            for vid, fm in accumulated.items()
            if len(fm.source_ranks) >= self._min_lists
        }

        # Sort by RRF score descending
        sorted_fused = sorted(
            qualifying.values(), key=lambda fm: fm.rrf_score, reverse=True
        )

        logger.debug(
            "rrf.fusion_complete",
            input_lists=n_lists,
            total_candidates=len(accumulated),
            qualifying=len(qualifying),
        )

        # Return RetrievalMatch objects with rrf_score as their score
        return [
            fm.match.model_copy(update={"score": fm.rrf_score})
            for fm in sorted_fused
        ]

    def fuse_with_provenance(
        self,
        ranked_lists: Sequence[list[RetrievalMatch]],
        list_names: list[str] | None = None,
    ) -> list[FusedMatch]:
        """
        Same as fuse() but returns FusedMatch objects with provenance data.

        Useful for debugging which retrieval strategies contributed to each result.
        """
        if not ranked_lists:
            return []

        n_lists = len(ranked_lists)
        names = list_names or [f"list_{i}" for i in range(n_lists)]
        weights = self._weights or [1.0] * n_lists

        accumulated: dict[str, FusedMatch] = {}

        for list_idx, (matches, name, weight) in enumerate(
            zip(ranked_lists, names, weights)
        ):
            for rank_0based, match in enumerate(matches):
                rank = rank_0based + 1
                rrf_contrib = weight / (self._k + rank)
                vid = match.vector_id

                if vid not in accumulated:
                    accumulated[vid] = FusedMatch(
                        vector_id=vid,
                        rrf_score=0.0,
                        match=match,
                    )

                accumulated[vid].rrf_score += rrf_contrib
                accumulated[vid].source_ranks[name] = rank
                accumulated[vid].source_scores[name] = match.score

        qualifying = {
            vid: fm
            for vid, fm in accumulated.items()
            if len(fm.source_ranks) >= self._min_lists
        }

        return sorted(
            qualifying.values(), key=lambda fm: fm.rrf_score, reverse=True
        )


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def rrf_fuse(
    *ranked_lists: list[RetrievalMatch],
    k: int = DEFAULT_K,
    weights: list[float] | None = None,
    list_names: list[str] | None = None,
) -> list[RetrievalMatch]:
    """
    Thin wrapper around RRFFusion for one-liner call sites.

    Example:
        merged = rrf_fuse(semantic_results, bm25_results, cpt_results, k=60)
    """
    return RRFFusion(k=k, weights=weights).fuse(list(ranked_lists), list_names)


def deduplicate_matches(matches: list[RetrievalMatch]) -> list[RetrievalMatch]:
    """
    Remove duplicate vector_ids, keeping the highest-scoring copy.

    Preserves original order of first occurrence of each id.
    """
    seen: set[str] = set()
    result: list[RetrievalMatch] = []
    for m in sorted(matches, key=lambda x: x.score, reverse=True):
        if m.vector_id not in seen:
            seen.add(m.vector_id)
            result.append(m)
    return result
