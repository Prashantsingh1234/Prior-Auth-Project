"""
Duplicate detection stage of the policy ingestion pipeline.

Detection strategy:
  1. Compute SHA-256 of the raw PDF bytes (done in pdf_parser.py)
  2. Query Pinecone for existing vectors tagged with that document_hash
  3. If found → return DuplicateCheckResult(is_duplicate=True, existing_policy_id=...)
  4. If not found → return DuplicateCheckResult(is_duplicate=False)

The hash check catches:
  - Exact re-submissions of the same file
  - Re-submissions under a different policy_id (prevents silent overwrites)

Version check (separate):
  If the same policy_id already exists in Pinecone with a DIFFERENT hash
  (i.e., a new version of a known policy), we allow ingestion but surface
  the existing version in the result so the caller can decide whether to
  replace or keep both.
"""

from __future__ import annotations

import structlog

from app.services.ingestion.models import DuplicateCheckResult
from app.services.vector.pinecone_client import PineconeClient

logger = structlog.get_logger(__name__)

_DEDUP_TOP_K = 1   # We only need to know if at least one match exists


class DuplicateDetector:
    """
    Detects duplicate policy documents via Pinecone metadata queries.

    Usage:
        detector = DuplicateDetector(pinecone_client)
        result = await detector.check(document_hash, policy_id, namespace)
    """

    def __init__(self, client: PineconeClient) -> None:
        self._client = client
        self._log = structlog.get_logger(self.__class__.__name__)

    async def check(
        self,
        document_hash: str,
        policy_id: str,
        namespace: str | None = None,
    ) -> DuplicateCheckResult:
        """
        Check whether this document hash or policy_id is already in the index.

        Returns:
            DuplicateCheckResult with is_duplicate=True if the exact same bytes
            were already ingested (regardless of policy_id).
        """
        # --- 1. Hash-based exact duplicate check ---
        hash_result = await self._query_by_hash(document_hash, namespace)
        if hash_result:
            existing_policy_id, existing_version = hash_result
            self._log.info(
                "dedup.exact_duplicate_found",
                document_hash=document_hash[:16],
                existing_policy_id=existing_policy_id,
            )
            return DuplicateCheckResult(
                is_duplicate=True,
                existing_policy_id=existing_policy_id,
                existing_version=existing_version,
                document_hash=document_hash,
            )

        self._log.info(
            "dedup.no_duplicate",
            document_hash=document_hash[:16],
            policy_id=policy_id,
        )
        return DuplicateCheckResult(
            is_duplicate=False,
            existing_policy_id=None,
            existing_version=None,
            document_hash=document_hash,
        )

    async def check_version_conflict(
        self,
        policy_id: str,
        document_hash: str,
        namespace: str | None = None,
    ) -> tuple[bool, str | None]:
        """
        Check whether a different version of this policy_id already exists.

        Returns:
            (conflict_exists, existing_document_hash | None)
        """
        try:
            stats = await self._client.describe_index_stats()
            ns_key = namespace or ""
            ns_info = stats.namespaces.get(ns_key, {})
            if not ns_info:
                return False, None
        except Exception:
            return False, None

        try:
            response = await self._client.query(
                vector=[0.0] * 1536,  # dummy vector — filter-only query
                top_k=_DEDUP_TOP_K,
                namespace=namespace,
                filter={"policy_id": {"$eq": policy_id}},
                include_metadata=True,
            )
        except Exception as err:
            self._log.warning("dedup.version_check_failed", error=str(err))
            return False, None

        matches = response.get("matches", [])
        if not matches:
            return False, None

        existing_hash = (matches[0].get("metadata") or {}).get("document_hash")
        if existing_hash and existing_hash != document_hash:
            return True, existing_hash
        return False, None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _query_by_hash(
        self,
        document_hash: str,
        namespace: str | None,
    ) -> tuple[str, str | None] | None:
        """
        Query Pinecone for any vector with metadata.document_hash == hash.

        Returns (policy_id, policy_version) of the first match, or None.
        """
        try:
            response = await self._client.query(
                vector=[0.0] * 1536,  # dummy — filter-only
                top_k=_DEDUP_TOP_K,
                namespace=namespace,
                filter={"document_hash": {"$eq": document_hash}},
                include_metadata=True,
            )
        except Exception as err:
            self._log.warning(
                "dedup.hash_query_failed",
                error=str(err),
                document_hash=document_hash[:16],
            )
            return None

        matches = response.get("matches", [])
        if not matches:
            return None

        meta = matches[0].get("metadata") or {}
        return meta.get("policy_id", "unknown"), meta.get("policy_version")
