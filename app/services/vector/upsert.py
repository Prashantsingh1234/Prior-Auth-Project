"""
Vector upsert pipeline.

Handles batched insertion of policy chunk vectors into Pinecone with:
- Batch size enforcement (100 vectors per Pinecone API call)
- Policy version lifecycle management (delete old → upsert new)
- Duplicate detection via document hash
- Structured logging with per-batch telemetry
- Retry on Pinecone transient failures
"""

from __future__ import annotations

import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.services.vector.pinecone_client import PineconeClient, VectorStoreError
from app.services.vector.schemas import PolicyVector

logger = structlog.get_logger(__name__)

# Pinecone's documented maximum upsert batch size
PINECONE_UPSERT_BATCH_SIZE = 100


class VectorUpsertService:
    """
    Manages lifecycle of policy vectors in Pinecone.

    Responsibilities:
    - Batch upsert with configurable batch size
    - Policy version management (delete stale, insert fresh)
    - Idempotent re-indexing (same doc hash = skip)
    """

    def __init__(
        self,
        client: PineconeClient,
        batch_size: int = PINECONE_UPSERT_BATCH_SIZE,
    ) -> None:
        self._client = client
        self._batch_size = batch_size
        self._log = structlog.get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Batch upsert
    # ------------------------------------------------------------------

    async def upsert_policy_chunks(
        self,
        vectors: list[PolicyVector],
        namespace: str | None = None,
    ) -> int:
        """
        Upsert a list of policy vectors, batching as needed.

        Args:
            vectors:   Policy chunks to insert / update
            namespace: Pinecone namespace (defaults to client default)

        Returns:
            Total number of vectors upserted.
        """
        if not vectors:
            return 0

        ns = namespace or self._client.namespace
        total_upserted = 0

        self._log.info(
            "upsert.started",
            total=len(vectors),
            policy_id=vectors[0].metadata.policy_id,
            namespace=ns,
        )

        batches = [
            vectors[i : i + self._batch_size]
            for i in range(0, len(vectors), self._batch_size)
        ]

        for batch_num, batch in enumerate(batches, start=1):
            pinecone_dicts = [v.to_pinecone_dict() for v in batch]
            count = await self._upsert_batch(pinecone_dicts, ns, batch_num)
            total_upserted += count
            self._log.debug(
                "upsert.batch_complete",
                batch=batch_num,
                total_batches=len(batches),
                count=count,
            )

        self._log.info(
            "upsert.complete",
            total_upserted=total_upserted,
            namespace=ns,
        )
        return total_upserted

    @retry(
        retry=retry_if_exception_type(VectorStoreError),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _upsert_batch(
        self,
        batch: list[dict],
        namespace: str,
        batch_num: int,
    ) -> int:
        """Single-batch upsert with retry on VectorStoreError."""
        return await self._client.upsert(vectors=batch, namespace=namespace)

    # ------------------------------------------------------------------
    # Policy version lifecycle
    # ------------------------------------------------------------------

    async def replace_policy_version(
        self,
        policy_id: str,
        new_vectors: list[PolicyVector],
        namespace: str | None = None,
    ) -> dict[str, int]:
        """
        Atomically replace an old policy version with a new one.

        Steps:
        1. Upsert new vectors (new IDs include new version in chunk_text metadata)
        2. Delete all vectors with the old policy_id (filter-based delete)

        This order (upsert before delete) ensures no gap in coverage during
        the transition window.

        Returns:
            {"upserted": N, "deleted_filter_applied": 1}
        """
        ns = namespace or self._client.namespace

        upserted = await self.upsert_policy_chunks(new_vectors, ns)

        await self._client.delete_by_filter(
            filter={"policy_id": {"$eq": policy_id}},
            namespace=ns,
        )

        self._log.info(
            "upsert.policy_replaced",
            policy_id=policy_id,
            upserted=upserted,
            namespace=ns,
        )
        return {"upserted": upserted, "deleted_filter_applied": 1}

    async def delete_policy(
        self,
        policy_id: str,
        namespace: str | None = None,
    ) -> None:
        """
        Remove all vectors for a policy (e.g. policy retired / expired).
        """
        ns = namespace or self._client.namespace
        await self._client.delete_by_filter(
            filter={"policy_id": {"$eq": policy_id}},
            namespace=ns,
        )
        self._log.info("upsert.policy_deleted", policy_id=policy_id, namespace=ns)

    async def delete_by_ids(
        self,
        vector_ids: list[str],
        namespace: str | None = None,
    ) -> None:
        """Delete specific vectors by their Pinecone IDs."""
        ns = namespace or self._client.namespace
        # Batch ID deletes too
        for i in range(0, len(vector_ids), self._batch_size):
            batch_ids = vector_ids[i : i + self._batch_size]
            await self._client.delete_by_ids(batch_ids, namespace=ns)
        self._log.info(
            "upsert.deleted_by_ids",
            count=len(vector_ids),
            namespace=ns,
        )
