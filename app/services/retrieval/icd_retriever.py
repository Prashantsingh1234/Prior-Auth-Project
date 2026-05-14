"""
ICD-10-CM aware retrieval with diagnosis code hierarchy expansion.

ICD-10-CM codes form a strict hierarchy:

    Category (3 chars)  →  Subcategory (4–5 chars)  →  Full code (5–7 chars)
    E11                 →  E11.9                    →  E11.9 (Type 2 DM, unspecified)

A policy for "E11" (Type 2 diabetes mellitus) covers all E11.x descendants.
Without hierarchy expansion, an exact-match filter on "E11.65" misses the
broader "E11" policy, even though it governs the same condition.

Expansion strategy:
  1. Exact code           — always included
  2. Parent subcategory   — strip last character group (E11.65 → E11.6)
  3. Category             — first 3 characters (E11.65 → E11)
  4. Block prefix         — first character + numeric range block (E → endocrine)
  5. Cross-references     — condition-level synonyms (DM type 1 ↔ type 2 for pump)

Usage:
    retriever = ICDRetriever(retrieval_service)
    results = await retriever.retrieve(
        query="CGM continuous glucose monitoring type 2 diabetes",
        icd_codes=["E11.65"],
        cpt_codes=["95249"],
        top_k=10,
    )
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

from app.services.vector.retrieval import RetrievalService
from app.services.vector.schemas import QueryResult, RetrievalMatch

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# ICD-10-CM hierarchy helpers
# ---------------------------------------------------------------------------

# Block-level description lookup (letter + numeric range → clinical domain)
# Used to build human-readable query augmentation, not for filtering.
ICD10_BLOCKS: dict[str, str] = {
    "A": "infectious_parasitic",
    "B": "infectious_parasitic",
    "C": "neoplasms",
    "D": "neoplasms_blood",
    "E": "endocrine_nutritional_metabolic",
    "F": "mental_behavioral",
    "G": "nervous_system",
    "H": "eye_ear",
    "I": "circulatory",
    "J": "respiratory",
    "K": "digestive",
    "L": "skin_subcutaneous",
    "M": "musculoskeletal",
    "N": "genitourinary",
    "O": "pregnancy_childbirth",
    "P": "perinatal",
    "Q": "congenital",
    "R": "symptoms_signs",
    "S": "injury_poisoning",
    "T": "injury_external_causes",
    "V": "external_causes",
    "W": "external_causes",
    "X": "external_causes",
    "Y": "external_causes",
    "Z": "factors_health_status",
}

# Manually curated cross-references for common PA use cases
# Maps ICD code prefix → related codes that share coverage policies
ICD_CROSS_REFS: dict[str, list[str]] = {
    # Type 2 diabetes with various complications → base code
    "E11": ["E11.9", "E11.65", "E11.649", "E11.641", "E11.51"],
    "E11.6": ["E11.65", "E11.649", "E11.641", "E11.610"],
    # Type 1 diabetes — CGM policies often cover both
    "E10": ["E11"],
    "E10.6": ["E11.6"],
    # Obesity for bariatric/GLP-1 PA
    "E66": ["E66.01", "E66.09", "E66.9"],
    "E66.0": ["E66.01", "E66.09"],
    # Heart failure
    "I50": ["I50.1", "I50.20", "I50.22", "I50.30", "I50.32", "I50.42"],
    # COPD / asthma for respiratory device PA
    "J44": ["J44.0", "J44.1"],
    "J45": ["J45.20", "J45.30", "J45.40", "J45.50", "J45.901"],
    # Sleep apnea for CPAP
    "G47": ["G47.30", "G47.31", "G47.33"],
    # Hypertension
    "I10": ["I10", "I11", "I12", "I13"],
}

# Maximum expanded codes to include in filter
MAX_EXPANDED_CODES = 25


# ---------------------------------------------------------------------------
# Hierarchy expansion
# ---------------------------------------------------------------------------

def _get_parents(code: str) -> list[str]:
    """
    Return progressively broader ancestor codes for an ICD-10-CM code.

    E11.649 → ["E11.64", "E11.6", "E11"]
    E11     → []
    """
    code = code.strip().upper()
    parents: list[str] = []

    # ICD-10 format: letter + 2 digits, optional dot, optional further chars
    # e.g. E11.649 → base="E11", suffix=".649"
    m = re.match(r"^([A-Z]\d{2})(\.?)(.*)$", code)
    if not m:
        return []

    base = m.group(1)  # E11
    dot = m.group(2)   # "."
    suffix = m.group(3)  # "649"

    if not suffix:
        # Already at 3-char category level — no parents
        return []

    # Walk from longest to shortest suffix
    full_suffix = suffix
    while len(full_suffix) > 0:
        full_suffix = full_suffix[:-1]
        if full_suffix:
            parents.append(f"{base}.{full_suffix}")
        else:
            parents.append(base)

    return parents


def expand_icd_codes(
    codes: list[str],
    *,
    include_parents: bool = True,
    include_cross_refs: bool = True,
    max_codes: int = MAX_EXPANDED_CODES,
) -> tuple[list[str], list[str]]:
    """
    Expand ICD-10 codes with hierarchy parents and cross-references.

    Returns:
        (expanded_codes, expansion_log)
    """
    expanded: set[str] = set(c.strip().upper() for c in codes)
    originals = [c.strip().upper() for c in codes]
    log: list[str] = []

    for code in originals:
        # Parent hierarchy
        if include_parents:
            for parent in _get_parents(code):
                if parent not in expanded:
                    expanded.add(parent)
                    log.append(f"parent: {code} → {parent}")

        # Cross-references
        if include_cross_refs:
            for prefix, refs in ICD_CROSS_REFS.items():
                if code.startswith(prefix):
                    for ref in refs:
                        if ref not in expanded:
                            expanded.add(ref)
                            log.append(f"cross_ref[{prefix}]: {code} → {ref}")

    # Prioritize originals, then sort
    extras = sorted(c for c in expanded if c not in set(originals))
    final = originals + extras

    if len(final) > max_codes:
        final = final[:max_codes]
        log.append(f"truncated to {max_codes} codes")

    return final, log


def build_icd_query_terms(codes: list[str]) -> list[str]:
    """
    Generate human-readable query augmentation terms from ICD codes.

    Used to enrich the dense retrieval query with condition vocabulary
    when the clinical summary may not use the exact code terminology.
    """
    terms: list[str] = []
    for code in codes:
        block_char = code[0].upper() if code else ""
        block_name = ICD10_BLOCKS.get(block_char, "")
        if block_name:
            terms.append(block_name.replace("_", " "))
    return list(dict.fromkeys(terms))  # deduplicate, preserve order


# ---------------------------------------------------------------------------
# ICDRetriever
# ---------------------------------------------------------------------------

@dataclass
class ICDRetrievalResult:
    """Result from an ICD-aware retrieval."""
    matches: list[RetrievalMatch]
    original_codes: list[str]
    expanded_codes: list[str]
    expansion_log: list[str]
    latency_ms: float


class ICDRetriever:
    """
    ICD-10-CM aware retrieval that expands the code hierarchy before searching.

    Augments the base hybrid_search() with:
      - Parent code expansion (E11.65 → E11.6, E11)
      - Cross-reference expansion (DM type 1 ↔ type 2 for shared policies)
      - Query term augmentation from ICD block names
    """

    def __init__(
        self,
        retrieval_service: RetrievalService,
        *,
        include_parent_expansion: bool = True,
        include_cross_refs: bool = True,
    ) -> None:
        self._svc = retrieval_service
        self._parents = include_parent_expansion
        self._xrefs = include_cross_refs
        self._log = structlog.get_logger(self.__class__.__name__)

    async def retrieve(
        self,
        query: str,
        icd_codes: list[str],
        cpt_codes: list[str] | None = None,
        *,
        top_k: int = 10,
        payer_name: str | None = None,
        namespace: str | None = None,
        augment_query: bool = True,
    ) -> ICDRetrievalResult:
        """
        Retrieve policy chunks relevant to the given ICD-10 codes.

        Args:
            query:         Base clinical query.
            icd_codes:     Original ICD-10 codes from the PA request.
            cpt_codes:     Optional CPT codes for co-filtering.
            top_k:         Max results to return.
            payer_name:    Optional payer filter.
            augment_query: Append ICD block terms to the query string for
                           richer dense retrieval.
        """
        import time
        t0 = time.perf_counter()

        if not icd_codes:
            self._log.warning("icd_retriever.no_codes")
            return ICDRetrievalResult(
                matches=[], original_codes=[], expanded_codes=[],
                expansion_log=[], latency_ms=0.0,
            )

        # 1. Expand ICD codes
        expanded, expansion_log = expand_icd_codes(
            icd_codes,
            include_parents=self._parents,
            include_cross_refs=self._xrefs,
        )

        self._log.debug(
            "icd_retriever.expanded",
            original_count=len(icd_codes),
            expanded_count=len(expanded),
        )

        try:
            from app.monitoring.metrics import ICD_EXPANSION_SIZE
            ICD_EXPANSION_SIZE.observe(len(expanded))
        except Exception:
            pass

        # 2. Optionally augment the query with clinical domain vocabulary
        effective_query = query
        if augment_query:
            extra_terms = build_icd_query_terms(icd_codes)
            if extra_terms:
                effective_query = f"{query} {' '.join(extra_terms)}"

        # 3. Hybrid search with expanded ICD filter
        try:
            result: QueryResult = await self._svc.hybrid_search(
                query=effective_query,
                cpt_codes=cpt_codes or [],
                icd_codes=expanded,
                top_k=top_k * 2,
                payer_name=payer_name,
                namespace=namespace,
                use_cache=True,
            )
        except Exception as exc:
            self._log.error("icd_retriever.search_failed", error=str(exc))
            raise

        # 4. Re-sort: exact original-code matches first
        original_set = set(c.upper() for c in icd_codes)

        def _sort_key(m: RetrievalMatch) -> tuple[int, int, float]:
            policy_icds = set(c.upper() for c in m.metadata.icd_codes)
            exact = 1 if policy_icds & original_set else 0
            # Second key: how specific the policy is (fewer ICD codes = more targeted)
            specificity = -len(policy_icds)
            return (-exact, specificity, -m.score)

        reranked = sorted(result.matches, key=_sort_key)[:top_k]

        latency_ms = (time.perf_counter() - t0) * 1000
        self._log.info(
            "icd_retriever.complete",
            icd_codes=icd_codes,
            expanded_count=len(expanded),
            results=len(reranked),
            latency_ms=round(latency_ms, 1),
        )

        return ICDRetrievalResult(
            matches=reranked,
            original_codes=[c.upper() for c in icd_codes],
            expanded_codes=expanded,
            expansion_log=expansion_log,
            latency_ms=latency_ms,
        )
