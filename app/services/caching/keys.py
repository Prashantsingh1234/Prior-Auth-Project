"""
Cache key builder and TTL constants.

All keys follow: pa:{CACHE_VERSION}:{domain}:{...identifiers}

The CACHE_VERSION prefix enables instant global cache invalidation
by bumping the version constant — all old keys become orphans and
expire naturally via TTL without requiring an explicit flush.
"""

from __future__ import annotations

import hashlib
import json


# Bump this to invalidate ALL cached data across every domain.
CACHE_VERSION = "v1"

# Namespace prefix — all PA platform keys share this root.
_NS = "pa"


# ---------------------------------------------------------------------------
# Per-domain TTL constants (seconds)
# ---------------------------------------------------------------------------

class TTL:
    """Domain-specific time-to-live values."""

    # Policy retrieval results: 30 min — policy content changes rarely but
    # cache shouldn't survive a routine re-index.
    RETRIEVAL: int = 1_800

    # LLM responses: 1 hour — deterministic prompts (temperature=0) produce
    # identical outputs; cache buys latency savings on repeated cases.
    LLM: int = 3_600

    # Embedding vectors: 24 hours — the same text + same model = same vector,
    # always. Safe to cache aggressively.
    EMBEDDING: int = 86_400

    # User sessions: 30 min — mirrors access_token_expire_minutes default.
    SESSION: int = 1_800

    # Revoked JWT tokens: 7 days — long enough to cover any refresh token TTL.
    TOKEN_REVOKED: int = 604_800

    # Clarification state: 2 hours — the provider has this long to respond.
    CLARIFICATION: int = 7_200

    # Case-level AI summary: 15 min — short TTL because a status change should
    # bust the cache before a reviewer sees stale data.
    CASE_SUMMARY: int = 900


# ---------------------------------------------------------------------------
# Key-building functions
# ---------------------------------------------------------------------------

def _key(*parts: str) -> str:
    """
    Assemble a namespaced, versioned Redis key.

    All non-string parts are coerced to str. Colons inside a segment are
    replaced with underscores to prevent accidental key-path splits.
    """
    safe = [str(p).replace(":", "_") for p in parts]
    return f"{_NS}:{CACHE_VERSION}:" + ":".join(safe)


def content_hash(value: str | bytes | list | dict) -> str:
    """
    Produce a stable 16-char hex digest for arbitrary content.

    Used to turn variable-length prompts or text into a fixed-length
    key segment. Uses SHA-256 truncated to 16 chars — collision probability
    is negligible for our data volumes.
    """
    if isinstance(value, (list, dict)):
        value = json.dumps(value, sort_keys=True, default=str)
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Domain key builders
# ---------------------------------------------------------------------------

def retrieval_key(cpt_codes: list[str], icd_codes: list[str], query: str) -> str:
    """
    Cache key for Pinecone/RAG retrieval results.

    Sorted codes ensure {"95249", "99213"} and {"99213", "95249"} hit the
    same cache entry.
    """
    fingerprint = content_hash({
        "cpt": sorted(cpt_codes),
        "icd": sorted(icd_codes),
        "q": query.strip().lower(),
    })
    return _key("retrieval", fingerprint)


def llm_key(model: str, prompt: str | list[dict]) -> str:
    """Cache key for LLM responses, scoped to model name + prompt hash."""
    return _key("llm", model, content_hash(prompt))


def embedding_key(model: str, text: str) -> str:
    """Cache key for embedding vectors. Same text + same model = same vector."""
    return _key("embedding", model, content_hash(text))


def session_key(user_id: str) -> str:
    """Cache key for a user's session payload."""
    return _key("session", user_id)


def token_revoked_key(jti: str) -> str:
    """
    Cache key for a revoked JWT token (identified by its 'jti' claim).

    Presence of this key signals the token is on the deny-list.
    """
    return _key("token", "revoked", jti)


def clarification_key(case_id: str, attempt: int) -> str:
    """Cache key for pending clarification state on a specific case + attempt."""
    return _key("clarification", case_id, str(attempt))


def case_summary_key(case_id: str) -> str:
    """Cache key for the AI-generated case evaluation summary."""
    return _key("case", "summary", case_id)


def case_invalidation_pattern(case_id: str) -> str:
    """
    Glob pattern to delete ALL cached entries for a case.

    Use with cache_delete_pattern() when a case transitions status
    or new documents are uploaded.
    """
    return f"{_NS}:{CACHE_VERSION}:*:{case_id}*"
