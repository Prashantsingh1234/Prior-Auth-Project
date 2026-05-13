"""
Pinecone connection and index management.

Wraps the synchronous Pinecone SDK in async-compatible helpers using
asyncio.to_thread() so the event loop is never blocked.

Initialization flow (called once at app startup):
    await init_pinecone()   # creates index if missing, validates connectivity
    ...
    await close_pinecone()  # graceful shutdown

All service code then calls:
    client = get_pinecone_client()
    index  = client.index

Index spec (serverless, cosine, 1536-dim for text-embedding-3-small):
    Cloud: AWS  |  Region: us-east-1  |  Metric: cosine
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions import PineconeException

from app.core.config.settings import get_settings
from app.core.exceptions.base import PABaseException
from app.services.vector.schemas import IndexStats

logger = structlog.get_logger(__name__)

# Module-level singleton
_pinecone_client: "PineconeClient | None" = None

# Default embedding dimension for text-embedding-3-small
DEFAULT_DIMENSION = 1536
DEFAULT_METRIC = "cosine"


class VectorStoreError(PABaseException):
    """Raised when the Pinecone API returns an unrecoverable error."""
    status_code = 503
    error_code = "VECTOR_STORE_ERROR"


class PineconeClient:
    """
    Async-friendly wrapper around the Pinecone Python SDK.

    Pinecone's SDK is synchronous. All blocking calls are delegated to a
    thread pool via asyncio.to_thread() so they never stall the event loop.
    """

    def __init__(
        self,
        api_key: str,
        index_name: str,
        namespace: str,
        dimension: int = DEFAULT_DIMENSION,
        metric: str = DEFAULT_METRIC,
    ) -> None:
        self._api_key = api_key
        self._index_name = index_name
        self._namespace = namespace
        self._dimension = dimension
        self._metric = metric
        self._pc: Pinecone | None = None
        self._index = None
        self._log = structlog.get_logger(
            self.__class__.__name__,
            index=index_name,
            namespace=namespace,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """
        Connect to Pinecone and ensure the target index exists.

        Creates the index (serverless / cosine) if it does not exist yet.
        Raises VectorStoreError on connectivity failures.
        """
        await asyncio.to_thread(self._sync_initialize)

    def _sync_initialize(self) -> None:
        try:
            self._pc = Pinecone(api_key=self._api_key)

            existing = [idx.name for idx in self._pc.list_indexes()]
            if self._index_name not in existing:
                self._log.info(
                    "pinecone.index.creating",
                    dimension=self._dimension,
                    metric=self._metric,
                )
                self._pc.create_index(
                    name=self._index_name,
                    dimension=self._dimension,
                    metric=self._metric,
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                )
                self._log.info("pinecone.index.created", index=self._index_name)
            else:
                self._log.info("pinecone.index.existing", index=self._index_name)

            self._index = self._pc.Index(self._index_name)
            self._log.info("pinecone.client.initialized")

        except PineconeException as exc:
            self._log.error("pinecone.init.failed", error=str(exc))
            raise VectorStoreError(details={"error": str(exc)}) from exc

    async def close(self) -> None:
        """Release the client. Called during app shutdown lifespan."""
        self._index = None
        self._pc = None
        logger.info("pinecone.client.closed")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def index(self):
        """The raw Pinecone Index handle. Use for upsert/query operations."""
        if self._index is None:
            raise RuntimeError(
                "PineconeClient not initialized. Call initialize() first."
            )
        return self._index

    @property
    def namespace(self) -> str:
        return self._namespace

    @property
    def dimension(self) -> int:
        return self._dimension

    # ------------------------------------------------------------------
    # Async index operations
    # ------------------------------------------------------------------

    async def describe_index_stats(self) -> IndexStats:
        """Return current index statistics (vector count, fullness, etc.)."""
        try:
            raw = await asyncio.to_thread(self.index.describe_index_stats)
            namespaces = {
                ns: info.vector_count
                for ns, info in (raw.namespaces or {}).items()
            }
            return IndexStats(
                total_vector_count=raw.total_vector_count or 0,
                dimension=raw.dimension or self._dimension,
                index_fullness=raw.index_fullness or 0.0,
                namespaces=namespaces,
            )
        except PineconeException as exc:
            raise VectorStoreError(details={"operation": "describe_stats"}) from exc

    async def upsert(
        self,
        vectors: list[dict[str, Any]],
        namespace: str | None = None,
    ) -> int:
        """
        Upsert a list of vector dicts.

        Args:
            vectors:   List of Pinecone-compatible vector dicts
                       (id, values, metadata, optional sparse_values)
            namespace: Target namespace (defaults to client default)

        Returns:
            Number of vectors upserted.
        """
        ns = namespace or self._namespace
        try:
            result = await asyncio.to_thread(
                self.index.upsert,
                vectors=vectors,
                namespace=ns,
            )
            upserted = result.upserted_count if result else len(vectors)
            self._log.info(
                "pinecone.upsert.complete",
                count=upserted,
                namespace=ns,
            )
            return upserted
        except PineconeException as exc:
            self._log.error("pinecone.upsert.failed", error=str(exc))
            raise VectorStoreError(details={"operation": "upsert"}) from exc

    async def query(
        self,
        vector: list[float],
        top_k: int,
        namespace: str | None = None,
        filter: dict | None = None,
        sparse_vector: dict | None = None,
        include_metadata: bool = True,
        include_values: bool = False,
    ) -> dict[str, Any]:
        """
        Execute a vector similarity query.

        Args:
            vector:       Dense query vector
            top_k:        Number of results to return
            namespace:    Target namespace
            filter:       Pinecone metadata filter dict
            sparse_vector: Sparse vector for hybrid search (indices + values)
            include_metadata: Include metadata in results
            include_values:   Include stored vector values in results

        Returns:
            Raw Pinecone query response dict.
        """
        ns = namespace or self._namespace
        query_kwargs: dict[str, Any] = dict(
            vector=vector,
            top_k=top_k,
            namespace=ns,
            include_metadata=include_metadata,
            include_values=include_values,
        )
        if filter:
            query_kwargs["filter"] = filter
        if sparse_vector:
            query_kwargs["sparse_vector"] = sparse_vector

        try:
            result = await asyncio.to_thread(self.index.query, **query_kwargs)
            return result.to_dict() if hasattr(result, "to_dict") else dict(result)
        except PineconeException as exc:
            self._log.error("pinecone.query.failed", error=str(exc))
            raise VectorStoreError(details={"operation": "query"}) from exc

    async def delete_by_ids(
        self,
        ids: list[str],
        namespace: str | None = None,
    ) -> None:
        """Delete vectors by their IDs."""
        ns = namespace or self._namespace
        try:
            await asyncio.to_thread(
                self.index.delete,
                ids=ids,
                namespace=ns,
            )
            self._log.info("pinecone.delete.by_ids", count=len(ids), namespace=ns)
        except PineconeException as exc:
            raise VectorStoreError(details={"operation": "delete_by_ids"}) from exc

    async def delete_by_filter(
        self,
        filter: dict,
        namespace: str | None = None,
    ) -> None:
        """Delete all vectors matching a metadata filter."""
        ns = namespace or self._namespace
        try:
            await asyncio.to_thread(
                self.index.delete,
                filter=filter,
                namespace=ns,
            )
            self._log.info("pinecone.delete.by_filter", filter=filter, namespace=ns)
        except PineconeException as exc:
            raise VectorStoreError(details={"operation": "delete_by_filter"}) from exc

    async def fetch(
        self,
        ids: list[str],
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Fetch specific vectors by ID."""
        ns = namespace or self._namespace
        try:
            result = await asyncio.to_thread(
                self.index.fetch,
                ids=ids,
                namespace=ns,
            )
            return result.to_dict() if hasattr(result, "to_dict") else dict(result)
        except PineconeException as exc:
            raise VectorStoreError(details={"operation": "fetch"}) from exc


# ---------------------------------------------------------------------------
# Module-level lifecycle functions (called from app lifespan)
# ---------------------------------------------------------------------------

async def init_pinecone() -> None:
    """
    Initialize the Pinecone client singleton.

    Called once during FastAPI startup lifespan.
    Logs a warning (rather than raising) if credentials are absent —
    the app can start without Pinecone for non-RAG operations.
    """
    global _pinecone_client

    settings = get_settings()
    if not settings.pinecone_api_key:
        logger.warning(
            "pinecone.init.skipped",
            reason="PINECONE_API_KEY not set — vector search unavailable",
        )
        return

    client = PineconeClient(
        api_key=settings.pinecone_api_key.get_secret_value(),
        index_name=settings.pinecone_index_name,
        namespace=settings.pinecone_namespace,
    )
    await client.initialize()
    _pinecone_client = client
    logger.info(
        "pinecone.initialized",
        index=settings.pinecone_index_name,
        namespace=settings.pinecone_namespace,
    )


async def close_pinecone() -> None:
    """Close the Pinecone client. Called during app shutdown."""
    global _pinecone_client
    if _pinecone_client is not None:
        await _pinecone_client.close()
        _pinecone_client = None


def get_pinecone_client() -> PineconeClient:
    """
    Return the initialized PineconeClient singleton.

    Raises RuntimeError if init_pinecone() was not called (or was skipped
    due to missing credentials).
    """
    if _pinecone_client is None:
        raise RuntimeError(
            "Pinecone client not initialized. "
            "Ensure PINECONE_API_KEY is set and init_pinecone() was called."
        )
    return _pinecone_client


async def get_pinecone_health() -> bool:
    """
    Lightweight health check. Returns True if the index is reachable.
    """
    if _pinecone_client is None:
        return False
    try:
        await _pinecone_client.describe_index_stats()
        return True
    except Exception:
        return False
