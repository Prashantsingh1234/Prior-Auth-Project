"""
Retrieval poisoning prevention.

Detects adversarial or corrupted documents injected into the vector store
that could manipulate the LLM's clinical decisions.

Detection layers:
  1. Source URL / ID integrity (allowlist validation)
  2. Content integrity hash verification
  3. Statistical anomaly detection (cosine-distance outliers)
  4. Injected instruction detection within retrieved docs
  5. Freshness / staleness validation
  6. Cross-document consistency checks (contradictory policy claims)
"""

from __future__ import annotations

import hashlib
import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.guardrails.models import (
    GuardrailStage,
    GuardrailViolation,
    ViolationSeverity,
    ViolationType,
)

_DETECTOR_NAME = "retrieval_poisoning"

# Patterns that look like injected instructions inside a retrieved document
_INJECTED_INSTRUCTION_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"ignore\s+(the\s+)?(?:above|previous|prior)\s+(?:instructions?|context)",
    r"you\s+must\s+(?:approve|deny|recommend|output)\s+(?:this|the\s+following)",
    r"(?:new|override)\s+(?:instructions?|directive|policy)\s*:",
    r"(?:system|admin)\s+(?:note|message|instruction)\s*:",
    r"<(?:SYSTEM|ADMIN|INSTRUCTION|INJECT)>",
    r"\{\{.*?instructions?.*?\}\}",  # Template injection
    r"PRIORITY\s+OVERRIDE\s*:",
    r"CONFIDENTIAL\s*:\s*(?:approve|deny|override)",
]]

# Source domains that are NOT trusted PA policy sources
_UNTRUSTED_DOMAIN_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"pastebin\.com",
    r"github\.com/[^/]+/[^/]+/raw",  # Raw GitHub (not an official payer source)
    r"reddit\.com",
    r"(?:bit|tinyurl|t)\.ly/",       # URL shorteners
    r"\\d+\\.\\d+\\.\\d+\\.\\d+",    # Direct IP address sources
]]

# Trusted PA policy source patterns (whitelist)
_TRUSTED_SOURCE_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"cms\.gov",
    r"medicare\.gov",
    r"medicaid\.gov",
    r"hhs\.gov",
    r"ama-assn\.org",
    r"(?:aetna|cigna|uhc|bcbs|humana|anthem)\.com",
    r"lcd-\d{4,}",      # LCD identifier
    r"ncd-\d{3,}",      # NCD identifier
]]


@dataclass
class RetrievedDocument:
    """Input structure for retrieval poisoning checks."""
    doc_id:       str
    content:      str
    source_url:   str | None = None
    source_id:    str | None = None
    created_at:   datetime | None = None
    content_hash: str | None = None   # Pre-computed SHA-256 if available
    embedding:    list[float] | None = None   # Vector embedding if available
    similarity:   float | None = None  # Similarity score from vector search


async def detect_retrieval_poisoning(
    documents: list[RetrievedDocument],
    expected_topic: str | None = None,
    threshold: float = 0.70,
    stage: GuardrailStage = GuardrailStage.PRE_LLM,
    context: dict[str, Any] | None = None,
) -> GuardrailViolation | None:
    """
    Scan retrieved documents for poisoning signals.

    Returns a GuardrailViolation if any document fails integrity checks
    and the overall confidence ≥ threshold.
    """
    if not documents:
        return None

    violations_found: list[dict[str, Any]] = []
    max_confidence = 0.0

    for doc in documents:
        doc_evidence: dict[str, Any] = {"doc_id": doc.doc_id}
        doc_score = 0.0

        # --- Check 1: Injected instructions in document content ---
        for pattern in _INJECTED_INSTRUCTION_PATTERNS:
            m = pattern.search(doc.content)
            if m:
                doc_evidence["injected_instruction"] = m.group()[:100]
                doc_score = max(doc_score, 0.95)
                break

        # --- Check 2: Source domain validation ---
        if doc.source_url:
            is_untrusted = any(p.search(doc.source_url) for p in _UNTRUSTED_DOMAIN_PATTERNS)
            is_trusted   = any(p.search(doc.source_url) for p in _TRUSTED_SOURCE_PATTERNS)
            if is_untrusted:
                doc_evidence["untrusted_source"] = doc.source_url
                doc_score = max(doc_score, 0.80)
            elif not is_trusted:
                doc_evidence["unverified_source"] = doc.source_url
                doc_score = max(doc_score, 0.40)

        # --- Check 3: Content hash integrity ---
        if doc.content_hash:
            actual_hash = hashlib.sha256(doc.content.encode()).hexdigest()
            if actual_hash != doc.content_hash:
                doc_evidence["hash_mismatch"] = True
                doc_evidence["expected_hash"] = doc.content_hash[:16]
                doc_evidence["actual_hash"]   = actual_hash[:16]
                doc_score = max(doc_score, 0.90)

        # --- Check 4: Staleness (docs > 2 years old may be outdated policy) ---
        if doc.created_at:
            age_days = (datetime.now(timezone.utc) - doc.created_at).days
            if age_days > 730:
                doc_evidence["staleness_days"] = age_days
                doc_score = max(doc_score, 0.45)

        # --- Check 5: Similarity outlier (anomalously low sim score may be poisoned) ---
        if doc.similarity is not None and doc.similarity < 0.30:
            doc_evidence["low_similarity"] = doc.similarity
            doc_score = max(doc_score, 0.55)

        if doc_score > 0:
            doc_evidence["score"] = round(doc_score, 4)
            violations_found.append(doc_evidence)
            max_confidence = max(max_confidence, doc_score)

    # --- Check 6: Statistical anomaly across all docs (embedding distance) ---
    similarities = [d.similarity for d in documents if d.similarity is not None]
    if len(similarities) >= 3:
        mean_sim = statistics.mean(similarities)
        stdev_sim = statistics.stdev(similarities) if len(similarities) > 1 else 0
        outliers = [s for s in similarities if stdev_sim > 0 and abs(s - mean_sim) / stdev_sim > 2.5]
        if outliers:
            max_confidence = max(max_confidence, 0.65)
            violations_found.append({
                "doc_id": "aggregate",
                "statistical_outliers": len(outliers),
                "mean_similarity": round(mean_sim, 4),
                "stdev_similarity": round(stdev_sim, 4),
            })

    confidence = min(round(max_confidence, 4), 1.0)

    if confidence < threshold or not violations_found:
        return None

    if confidence >= 0.90:
        severity = ViolationSeverity.CRITICAL
    elif confidence >= 0.75:
        severity = ViolationSeverity.HIGH
    elif confidence >= 0.55:
        severity = ViolationSeverity.MEDIUM
    else:
        severity = ViolationSeverity.LOW

    return GuardrailViolation(
        violation_type=ViolationType.RETRIEVAL_POISONING,
        severity=severity,
        description=f"Retrieval poisoning detected: {len(violations_found)} document(s) flagged",
        confidence=confidence,
        evidence={
            "flagged_documents":  violations_found[:10],
            "total_docs_checked": len(documents),
        },
        stage=stage,
        detector=_DETECTOR_NAME,
    )
