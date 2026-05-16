"""
Policy grounding validator.

Verifies that LLM-generated PA decisions are grounded in retrieved policy
documents.  An ungrounded decision — one that makes coverage claims without
citing a policy — is a hallucination risk and a compliance failure.

Checks:
  1. Minimum citation count (e.g., at least 1 policy document cited)
  2. Policy ID format validation (known ID patterns)
  3. Coverage ratio — what fraction of claims reference a retrieved document
  4. Claim-without-evidence patterns (absolute statements with no citation)
"""

from __future__ import annotations

import re
from typing import Any

from app.guardrails.models import (
    GuardrailStage,
    GuardrailViolation,
    ViolationSeverity,
    ViolationType,
)

_DETECTOR_NAME = "policy_grounding"

# ---------------------------------------------------------------------------
# Citation patterns — what a properly grounded response looks like
# ---------------------------------------------------------------------------

_CITATION_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"(?:per|according\s+to|based\s+on|as\s+per|per\s+the|see)\s+(?:policy|guideline|criteria|LCD|NCD|coverage)\s+[\w\-\.]+",
    r"(?:policy|coverage|LCD|NCD|guideline)\s+(?:number|#|id|code)?\s*[:=]?\s*[\w\-\.]{4,}",
    r"\bLCD-?\d{4,}\b",          # Local Coverage Determination
    r"\bNCD-?\d{3}\b",           # National Coverage Determination
    r"\bCPT\s*\d{5}\b",          # CPT code citation
    r"\bICD-?(?:10|11)-?[A-Z]\d{2,3}(?:\.\d+)?\b",   # ICD code citation
    r"\bHCPCS\s+[A-Z]\d{4}\b",   # HCPCS code
    r"\(Source:\s*[^)]{5,80}\)",  # Explicit (Source: ...) citation
    r"\[Reference:\s*[^\]]{5,80}\]",
    r"Document\s+(?:ID|#|Reference)\s*[:=]\s*[\w\-]+",
    r"\bpage\s+\d+\s+of\s+the\s+(?:policy|guideline|coverage\s+document)\b",
]]

# Statements that REQUIRE grounding but often lack it
_UNGROUNDED_CLAIM_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"(?:this\s+(?:service|procedure|treatment|medication)\s+is\s+(?:covered|not\s+covered|excluded|included))",
    r"(?:medical\s+necessity\s+(?:criteria|requirements?)\s+(?:are|have\s+been)\s+(?:met|not\s+met|satisfied))",
    r"(?:the\s+(?:plan|policy|insurer|payer)\s+(?:covers?|does\s+not\s+cover|excludes?))",
    r"(?:authorization\s+is\s+(?:approved|denied|recommended\s+for\s+(?:approval|denial)))",
    r"(?:clinical\s+criteria\s+(?:support|do\s+not\s+support)\s+(?:approval|denial))",
    r"(?:the\s+(?:requested|proposed)\s+(?:service|procedure|treatment)\s+(?:meets?|does\s+not\s+meet))",
]]


async def detect_policy_grounding_failure(
    text: str,
    retrieved_doc_ids: list[str] | None = None,
    min_citations: int = 1,
    threshold: float = 0.60,
    stage: GuardrailStage = GuardrailStage.POST_LLM,
    context: dict[str, Any] | None = None,
) -> GuardrailViolation | None:
    """
    Verify that LLM output is grounded in retrieved policy documents.

    Args:
        text:              LLM-generated decision text.
        retrieved_doc_ids: IDs of documents retrieved and passed to the LLM.
        min_citations:     Minimum number of distinct citations required.
        threshold:         Minimum grounding_failure_score to fire.
        stage:             Pipeline stage.

    Returns GuardrailViolation if grounding score ≥ threshold, else None.
    """
    if not text or not text.strip():
        return None

    evidence: dict[str, Any] = {}

    # Count citations found in output
    found_citations: list[str] = []
    for pattern in _CITATION_PATTERNS:
        for m in pattern.finditer(text):
            found_citations.append(m.group())

    citation_count  = len(set(found_citations))
    evidence["citation_count"] = citation_count
    evidence["citations_found"] = list(set(found_citations))[:10]

    # Count coverage claims that need grounding
    claim_count = sum(1 for p in _UNGROUNDED_CLAIM_PATTERNS if p.search(text))
    evidence["coverage_claims_count"] = claim_count

    # Cross-reference with retrieved docs
    grounding_match_count = 0
    if retrieved_doc_ids:
        for doc_id in retrieved_doc_ids:
            if doc_id in text or doc_id.lower() in text.lower():
                grounding_match_count += 1
    evidence["retrieved_docs_referenced"] = grounding_match_count
    evidence["retrieved_doc_count"] = len(retrieved_doc_ids or [])

    # Compute grounding failure score
    failure_score = 0.0

    # No citations at all
    if citation_count == 0 and claim_count > 0:
        failure_score = 0.90

    # Below minimum citation count
    elif citation_count < min_citations and claim_count > 0:
        deficit = min_citations - citation_count
        failure_score = 0.50 + (deficit * 0.15)

    # Claims without retrieved document references
    elif retrieved_doc_ids and grounding_match_count == 0 and claim_count > 0:
        failure_score = 0.70

    # Partial grounding (some citations but low ratio)
    elif claim_count > 0:
        citation_ratio = citation_count / max(claim_count, 1)
        if citation_ratio < 0.5:
            failure_score = 0.45 + (0.5 - citation_ratio) * 0.5

    failure_score = min(round(failure_score, 4), 1.0)
    evidence["grounding_failure_score"] = failure_score

    if failure_score < threshold:
        return None

    if failure_score >= 0.85:
        severity = ViolationSeverity.HIGH
    elif failure_score >= 0.65:
        severity = ViolationSeverity.MEDIUM
    else:
        severity = ViolationSeverity.LOW

    return GuardrailViolation(
        violation_type=ViolationType.POLICY_GROUNDING_FAILURE,
        severity=severity,
        description=(
            f"Policy grounding failure: {citation_count} citations for {claim_count} coverage claims "
            f"(failure_score={failure_score:.2f})"
        ),
        confidence=failure_score,
        evidence=evidence,
        stage=stage,
        detector=_DETECTOR_NAME,
    )
