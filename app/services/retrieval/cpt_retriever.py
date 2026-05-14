"""
CPT-aware retrieval with code hierarchy expansion.

CPT codes are organized in numeric ranges by category.  When a query
contains "95249" (ambulatory CGM), policies for related codes in the
same category (95250, 95251) are also relevant.  Without expansion, a
strict metadata filter on the exact code misses adjacent criteria.

Expansion strategy:
  1. Exact match        — always included
  2. Numeric range      — ±N codes around the query code within the same category
  3. Category siblings  — all codes in the same CPT category bucket
  4. Cross-references   — manually curated pairs (e.g. CGM ↔ insulin pump)

The expanded code set is fed into a hybrid_search() call with a broader
metadata filter, then re-scored by how closely the policy codes match the
original (unexpanded) query codes.

Usage:
    retriever = CPTRetriever(retrieval_service)
    results = await retriever.retrieve(
        query="CGM coverage for type 2 diabetes",
        cpt_codes=["95249"],
        icd_codes=["E11.9"],
        top_k=10,
    )
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import structlog

from app.services.vector.retrieval import RetrievalService
from app.services.vector.schemas import QueryResult, RetrievalMatch

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# CPT category buckets (ranges, inclusive)
# Each bucket covers a clinical domain; codes within the same bucket are
# often governed by the same or related coverage policies.
# ---------------------------------------------------------------------------

CPT_CATEGORIES: list[tuple[int, int, str]] = [
    # (range_start, range_end, category_name)
    (10004, 19499, "surgery_integumentary"),
    (20000, 29999, "surgery_musculoskeletal"),
    (30000, 32999, "surgery_respiratory"),
    (33000, 37799, "surgery_cardiovascular"),
    (40000, 49999, "surgery_digestive"),
    (50000, 59999, "surgery_urinary"),
    (60000, 69999, "surgery_endocrine_eye_ear"),
    (70000, 79999, "radiology"),
    (80000, 89399, "lab_pathology"),
    (90000, 99499, "evaluation_management"),
    (90281, 90399, "immunology"),
    (90460, 90474, "vaccines"),
    (92000, 92499, "ophthalmology"),
    (93000, 93799, "cardiology"),
    (94000, 94799, "pulmonary"),
    (95000, 95999, "neurology_allergy"),  # includes CGM codes 95249-95251
    (96000, 96020, "neuropsychology"),
    (96100, 96146, "psychological_testing"),
    (96150, 96161, "health_behavior"),
    (97000, 97799, "physical_medicine"),
    (99000, 99091, "special_services"),
    (99091, 99091, "home_monitoring"),
    (99201, 99499, "em_office_hospital"),
]

# ---------------------------------------------------------------------------
# Manually curated cross-references
# Maps CPT code → related CPT codes that often appear in the same policy.
# ---------------------------------------------------------------------------

CPT_CROSS_REFS: dict[str, list[str]] = {
    # CGM / Continuous Glucose Monitoring
    "95249": ["95250", "95251", "99091", "E0787"],
    "95250": ["95249", "95251", "99091"],
    "95251": ["95249", "95250"],
    # Insulin pumps
    "95250": ["E0784", "E0787"],
    "E0784": ["95249", "95250", "95251", "E0787"],
    "E0787": ["95249", "95250", "95251", "E0784"],
    # Cardiac monitoring
    "93241": ["93242", "93243", "93244", "93245", "93246", "93247", "93248"],
    # CPAP / sleep
    "94660": ["94662", "E0601"],
    "E0601": ["94660", "94662"],
}

# Numeric range expansion: include codes ± this many positions
CODE_RANGE_RADIUS = 3

# Max number of expanded codes to include in filter (prevent Pinecone filter bloat)
MAX_EXPANDED_CODES = 20


# ---------------------------------------------------------------------------
# Code expansion logic
# ---------------------------------------------------------------------------

def _parse_numeric(code: str) -> int | None:
    """Extract numeric portion of a CPT code (strips trailing letters)."""
    m = re.match(r"^(\d+)", code.strip())
    return int(m.group(1)) if m else None


def _find_category(numeric: int) -> str | None:
    for start, end, name in CPT_CATEGORIES:
        if start <= numeric <= end:
            return name
    return None


def expand_cpt_codes(
    codes: list[str],
    *,
    include_range: bool = True,
    include_cross_refs: bool = True,
    max_codes: int = MAX_EXPANDED_CODES,
) -> tuple[list[str], list[str]]:
    """
    Expand a list of CPT codes to include related codes.

    Returns:
        (expanded_codes, expansion_log)
        expanded_codes: original + expanded codes, deduplicated, capped at max_codes
        expansion_log: human-readable list of expansion steps (for debugging)
    """
    expanded: set[str] = set(codes)
    log: list[str] = []

    for code in codes:
        numeric = _parse_numeric(code)

        # Numeric range expansion
        if include_range and numeric is not None:
            for delta in range(-CODE_RANGE_RADIUS, CODE_RANGE_RADIUS + 1):
                neighbor = numeric + delta
                category = _find_category(neighbor)
                if category and category == _find_category(numeric):
                    neighbor_code = str(neighbor)
                    if neighbor_code not in expanded:
                        expanded.add(neighbor_code)
                        log.append(f"range_expand: {code} → {neighbor_code}")

        # Cross-reference expansion
        if include_cross_refs:
            refs = CPT_CROSS_REFS.get(code, [])
            for ref in refs:
                if ref not in expanded:
                    expanded.add(ref)
                    log.append(f"cross_ref: {code} → {ref}")

    # Prioritize original codes, then sort numerics, then non-numerics
    originals = list(codes)
    extras = [c for c in sorted(expanded) if c not in originals]
    final = originals + extras

    if len(final) > max_codes:
        final = final[:max_codes]
        log.append(f"truncated to {max_codes} codes")

    return final, log


# ---------------------------------------------------------------------------
# CPTRetriever
# ---------------------------------------------------------------------------

@dataclass
class CPTRetrievalResult:
    """Result from a CPT-aware retrieval."""
    matches: list[RetrievalMatch]
    original_codes: list[str]
    expanded_codes: list[str]
    expansion_log: list[str]
    latency_ms: float


class CPTRetriever:
    """
    CPT-aware retrieval that expands code sets before searching.

    Wraps the base RetrievalService.hybrid_search() with code expansion
    pre-processing and a post-filter that boosts results with exact
    original-code matches.
    """

    def __init__(
        self,
        retrieval_service: RetrievalService,
        *,
        include_range_expansion: bool = True,
        include_cross_refs: bool = True,
    ) -> None:
        self._svc = retrieval_service
        self._range = include_range_expansion
        self._xrefs = include_cross_refs
        self._log = structlog.get_logger(self.__class__.__name__)

    async def retrieve(
        self,
        query: str,
        cpt_codes: list[str],
        icd_codes: list[str] | None = None,
        *,
        top_k: int = 10,
        payer_name: str | None = None,
        namespace: str | None = None,
    ) -> CPTRetrievalResult:
        """
        Retrieve policy chunks relevant to the given CPT codes.

        Steps:
          1. Expand CPT codes with range and cross-reference expansion.
          2. Run hybrid_search with expanded code filter.
          3. Re-sort: exact code matches first, then by vector score.

        Args:
            query:     Clinical question or summary (for dense retrieval).
            cpt_codes: Original CPT codes from the PA request.
            icd_codes: Optional ICD codes for co-filtering.
            top_k:     Maximum results to return.
            payer_name: Optional payer filter.
        """
        import time
        t0 = time.perf_counter()

        if not cpt_codes:
            self._log.warning("cpt_retriever.no_codes")
            return CPTRetrievalResult(
                matches=[], original_codes=[], expanded_codes=[],
                expansion_log=[], latency_ms=0.0,
            )

        # 1. Expand codes
        expanded, expansion_log = expand_cpt_codes(
            cpt_codes,
            include_range=self._range,
            include_cross_refs=self._xrefs,
        )

        self._log.debug(
            "cpt_retriever.expanded",
            original_count=len(cpt_codes),
            expanded_count=len(expanded),
        )

        try:
            from app.monitoring.metrics import CPT_EXPANSION_SIZE
            CPT_EXPANSION_SIZE.observe(len(expanded))
        except Exception:
            pass

        # 2. Hybrid search with expanded filter
        try:
            result: QueryResult = await self._svc.hybrid_search(
                query=query,
                cpt_codes=expanded,
                icd_codes=icd_codes or [],
                top_k=top_k * 2,  # over-fetch before re-ranking
                payer_name=payer_name,
                namespace=namespace,
                use_cache=True,
            )
        except Exception as exc:
            self._log.error("cpt_retriever.search_failed", error=str(exc))
            raise

        # 3. Re-sort: boost exact original-code matches
        original_set = set(cpt_codes)
        def _sort_key(m: RetrievalMatch) -> tuple[int, float]:
            policy_cpts = set(m.metadata.cpt_codes)
            exact = 1 if policy_cpts & original_set else 0
            return (-exact, -m.score)

        reranked = sorted(result.matches, key=_sort_key)[:top_k]

        latency_ms = (time.perf_counter() - t0) * 1000
        self._log.info(
            "cpt_retriever.complete",
            cpt_codes=cpt_codes,
            expanded_count=len(expanded),
            results=len(reranked),
            latency_ms=round(latency_ms, 1),
        )

        return CPTRetrievalResult(
            matches=reranked,
            original_codes=cpt_codes,
            expanded_codes=expanded,
            expansion_log=expansion_log,
            latency_ms=latency_ms,
        )
