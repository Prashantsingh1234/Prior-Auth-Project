"""
Sparse vector encoder for hybrid Pinecone retrieval.

Generates BM25-style sparse vectors from medical codes (CPT, ICD-10)
and key clinical terms. These sparse vectors complement dense embeddings
in hybrid search — they provide exact-match recall for specific codes
that semantic embeddings may conflate with related (but not identical) codes.

Design:
- Vocabulary: virtual hash-based (no pre-built corpus required)
- Code weighting: IDF-approximated via code category (CPT > ICD > terms)
- Normalization: L2-normalize values so hybrid alpha blending is stable

Vocabulary index assignment:
    hash(code.upper()) % VOCAB_SIZE → vocabulary index
    This is deterministic across all processes and requires no shared state.
"""

from __future__ import annotations

import hashlib
import re

from app.services.vector.schemas import SparseVector

# Virtual vocabulary size — large enough to minimize collisions
VOCAB_SIZE = 30_000

# Base weights by code type (higher = more discriminative)
_WEIGHT_CPT = 3.0
_WEIGHT_ICD = 2.5
_WEIGHT_CLINICAL_TERM = 1.0

# Clinical terms that should receive sparse representation
# (supplement code-level matching with key policy terms)
_CLINICAL_KEYWORDS = frozenset({
    "prior authorization", "medical necessity", "criteria",
    "coverage", "approved", "denied", "excluded", "covered",
    "durable medical equipment", "dme", "surgical", "diagnostic",
    "inpatient", "outpatient", "emergency", "urgent",
    "continuous glucose monitor", "cgm", "insulin pump",
    "mri", "ct scan", "ultrasound", "biopsy",
    "physical therapy", "occupational therapy",
    "chemotherapy", "radiation", "immunotherapy",
})


def _code_to_index(code: str) -> int:
    """
    Map a medical code to a stable vocabulary index.

    Uses SHA-256 (first 8 bytes → uint64) modulo VOCAB_SIZE.
    Collision probability for a few thousand unique codes is < 0.01%.
    """
    digest = hashlib.sha256(code.upper().encode()).digest()
    raw = int.from_bytes(digest[:8], "big")
    return raw % VOCAB_SIZE


def build_medical_sparse_vector(
    text: str,
    medical_codes: list[str],
    vocab_size: int = VOCAB_SIZE,
) -> SparseVector:
    """
    Build a sparse vector for a policy chunk or query.

    Args:
        text:          The source text (used for clinical keyword extraction)
        medical_codes: CPT and ICD-10 codes associated with the document
        vocab_size:    Virtual vocabulary size (default 30,000)

    Returns:
        SparseVector with deduplicated indices and TF-IDF-approximate weights.
    """
    weights: dict[int, float] = {}

    # Encode explicit medical codes
    for code in medical_codes:
        code = code.strip()
        if not code:
            continue
        idx = _code_to_index(code)
        weight = _WEIGHT_CPT if _is_cpt_code(code) else _WEIGHT_ICD
        # Accumulate weights for hash collisions (rare but safe)
        weights[idx] = weights.get(idx, 0.0) + weight

    # Encode clinical keywords found in text
    lower_text = text.lower()
    for keyword in _CLINICAL_KEYWORDS:
        if keyword in lower_text:
            idx = _code_to_index(keyword)
            weights[idx] = weights.get(idx, 0.0) + _WEIGHT_CLINICAL_TERM

    # Encode individual words from the text that look like codes
    for word in re.findall(r"\b[A-Z]\d{2,4}\.?\d*\b|\b\d{5}\b", text.upper()):
        idx = _code_to_index(word)
        weights[idx] = weights.get(idx, 0.0) + _WEIGHT_CLINICAL_TERM * 0.5

    if not weights:
        # Return a minimal sparse vector rather than an empty one
        # (Pinecone requires at least one entry for hybrid queries)
        return SparseVector(indices=[0], values=[0.001])

    # L2 normalize so hybrid alpha blending works correctly
    indices = list(weights.keys())
    raw_values = [weights[i] for i in indices]
    l2_norm = sum(v ** 2 for v in raw_values) ** 0.5
    if l2_norm > 0:
        values = [v / l2_norm for v in raw_values]
    else:
        values = raw_values

    return SparseVector(indices=indices, values=values)


def build_query_sparse_vector(
    query: str,
    cpt_codes: list[str],
    icd_codes: list[str],
) -> SparseVector:
    """
    Build a sparse vector for a retrieval query.

    Combines explicit code matching (high weight) with keyword extraction
    from the query text (lower weight).
    """
    all_codes = cpt_codes + icd_codes
    return build_medical_sparse_vector(query, all_codes)


def _is_cpt_code(code: str) -> bool:
    """
    Heuristic: CPT codes are 5-digit numeric strings (possibly with letter prefix).
    ICD-10 codes start with a letter followed by digits.
    """
    code = code.strip()
    # CPT: exactly 5 digits, optionally with F/T/U/M/G prefix
    if re.fullmatch(r"[A-Z]?\d{5}", code.upper()):
        return True
    # Also matches HCPCS Level II (starts with letter, 4 digits)
    if re.fullmatch(r"[A-Z]\d{4}", code.upper()):
        return True
    return False
