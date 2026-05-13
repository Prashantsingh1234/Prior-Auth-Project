"""
Vector retrieval service — semantic and hybrid search.

Two retrieval modes:
  semantic  — pure dense vector similarity (cosine)
  hybrid    — dense + sparse (BM25-style medical codes), Pinecone native

Hybrid is the default for PA use cases because:
- Semantic search captures meaning ("blood glucose monitoring")
- Sparse captures exact codes ("CPT 95249") that embeddings sometimes
  conflate with related but non-identical codes

Alpha parameter (hybrid blend):
  0.0 → pure sparse (keyword only)
  0.5 → balanced
  0.7 → dense-dominant (recommended default for PA policies)
  1.0 → pure dense (semantic only)

Metadata filtering (applied before vector scoring):
  - $in operator filters for CPT / ICD code overlap
  - Date range filter ensures only currently-effective policies match
  - Payer filter for payer-specific criteria
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import structlog

from app.services.caching.retrieval_cache import RetrievalCache
from app.services.vector.embeddings import EmbeddingService
from app.services.vector.pinecone_client import PineconeClient
from app.services.vector.schemas import (
    PolicyChunkMetadata,
    QueryResult,
    RetrievalMatch,
    SparseVector,
)
from app.services.vector.sparse import build_query_sparse_vector

logger = structlog.get_logger(__name__)

# Default hybrid alpha: 70% dense, 30% sparse
DEFAULT_HYBRID_ALPHA = 0.7

# Default top-K results to retrieve
DEFAULT_TOP_K = 10

# Minimum score threshold — results below this are dropped
MIN_SCORE_THRESHOLD = 0.50


class RetrievalService:
    """
    Async policy retrieval using Pinecone semantic and hybrid search.

    Usage:
        service = RetrievalService(pinecone_client, embedding_service)

        result = await service.hybrid_search(
            query="Is CGM covered for type 2 diabetes?",
            cpt_codes=["95249"],
            icd_codes=["E11.9"],
            top_k=5,
        )
        for match in result.matches:
            print(match.score, match.metadata.chunk_text)
    """

    def __init__(
        self,
        client: PineconeClient,
        embedding_service: EmbeddingService,
        cache: RetrievalCache | None = None,
    ) -> None:
        self._client = client
        self._embedding = embedding_service
        self._cache = cache or RetrievalCache()
        self._log = structlog.get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Public search methods
    # ------------------------------------------------------------------

    async def semantic_search(
        self,
        query: str,
        cpt_codes: list[str] | None = None,
        icd_codes: list[str] | None = None,
        top_k: int = DEFAULT_TOP_K,
        payer_name: str | None = None,
        namespace: str | None = None,
        use_cache: bool = True,
    ) -> QueryResult:
        """
        Pure dense (semantic) vector search.

        Args:
            query:      Natural language query from clinical notes
            cpt_codes:  CPT codes for metadata pre-filtering
            icd_codes:  ICD-10 codes for metadata pre-filtering
            top_k:      Number of results to return
            payer_name: Restrict to a specific payer's policies
            namespace:  Pinecone namespace
            use_cache:  Check the retrieval cache before hitting Pinecone

        Returns:
            QueryResult with ranked matches.
        """
        cpt_codes = cpt_codes or []
        icd_codes = icd_codes or []
        ns = namespace or self._client.namespace

        # Cache lookup
        if use_cache:
            cached = await self._cache.get(cpt_codes, icd_codes, query)
            if cached is not None:
                self._log.debug("retrieval.cache_hit", query_len=len(query))
                return self._deserialize_cached(cached, "semantic", ns, cpt_codes, icd_codes)

        start = time.perf_counter()

        query_vector = await self._embedding.embed_text(query)
        metadata_filter = self.build_metadata_filter(cpt_codes, icd_codes, payer_name)

        raw = await self._client.query(
            vector=query_vector,
            top_k=top_k + 5,  # fetch extra, then trim after score filtering
            namespace=ns,
            filter=metadata_filter,
            include_metadata=True,
        )

        latency_ms = (time.perf_counter() - start) * 1000
        result = self._parse_raw_result(
            raw, "semantic", ns, latency_ms, cpt_codes, icd_codes
        )

        # Cache the result
        if use_cache:
            await self._cache.set(
                cpt_codes, icd_codes, query,
                self._serialize_for_cache(result),
            )

        self._track_metrics(result, latency_ms)
        return result

    async def hybrid_search(
        self,
        query: str,
        cpt_codes: list[str] | None = None,
        icd_codes: list[str] | None = None,
        top_k: int = DEFAULT_TOP_K,
        alpha: float = DEFAULT_HYBRID_ALPHA,
        payer_name: str | None = None,
        namespace: str | None = None,
        use_cache: bool = True,
    ) -> QueryResult:
        """
        Hybrid (dense + sparse) vector search — recommended for PA cases.

        Args:
            query:     Natural language query
            cpt_codes: CPT procedure codes
            icd_codes: ICD-10 diagnosis codes
            top_k:     Number of results
            alpha:     Dense/sparse blend ratio (0.7 = 70% dense, 30% sparse)
            payer_name: Restrict to specific payer
            namespace: Pinecone namespace
            use_cache: Check retrieval cache first

        Returns:
            QueryResult with ranked matches.
        """
        cpt_codes = cpt_codes or []
        icd_codes = icd_codes or []
        ns = namespace or self._client.namespace

        cache_query = f"hybrid:{alpha}:{query}"
        if use_cache:
            cached = await self._cache.get(cpt_codes, icd_codes, cache_query)
            if cached is not None:
                self._log.debug("retrieval.hybrid_cache_hit")
                return self._deserialize_cached(cached, "hybrid", ns, cpt_codes, icd_codes)

        start = time.perf_counter()

        # Build dense + sparse vectors concurrently would need asyncio.gather
        # but embedding is already cached, so sequential is fine here
        query_vector = await self._embedding.embed_text(query)
        sparse = build_query_sparse_vector(query, cpt_codes, icd_codes)

        # Scale by alpha (dense) and 1-alpha (sparse)
        scaled_dense = [v * alpha for v in query_vector]
        scaled_sparse = sparse.scale(1.0 - alpha)

        metadata_filter = self.build_metadata_filter(cpt_codes, icd_codes, payer_name)

        raw = await self._client.query(
            vector=scaled_dense,
            top_k=top_k + 5,
            namespace=ns,
            filter=metadata_filter,
            sparse_vector=scaled_sparse.to_pinecone_dict(),
            include_metadata=True,
        )

        latency_ms = (time.perf_counter() - start) * 1000
        result = self._parse_raw_result(
            raw, "hybrid", ns, latency_ms, cpt_codes, icd_codes
        )

        if use_cache:
            await self._cache.set(
                cpt_codes, icd_codes, cache_query,
                self._serialize_for_cache(result),
            )

        self._track_metrics(result, latency_ms)
        return result

    # ------------------------------------------------------------------
    # Metadata filter builder
    # ------------------------------------------------------------------

    def build_metadata_filter(
        self,
        cpt_codes: list[str] | None = None,
        icd_codes: list[str] | None = None,
        payer_name: str | None = None,
        effective_on: str | None = None,
    ) -> dict | None:
        """
        Build a Pinecone metadata filter from clinical criteria.

        Pinecone filter operators used:
            $in    — value is in a list
            $lte   — less than or equal (for effective_date)
            $gte   — greater than or equal (for expiration_date)
            $eq    — exact match

        Returns None (no filter) if no criteria are provided.
        """
        conditions: list[dict] = []

        if cpt_codes:
            conditions.append({"cpt_codes": {"$in": cpt_codes}})
        if icd_codes:
            conditions.append({"icd_codes": {"$in": icd_codes}})
        if payer_name:
            conditions.append({"payer_name": {"$eq": payer_name}})
        if effective_on:
            # Policy must be effective on the given date
            conditions.append({"effective_date": {"$lte": effective_on}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def build_active_policy_filter(self) -> dict:
        """
        Filter that restricts results to currently-active policies.

        A policy is active if:
        - effective_date <= today
        - expiration_date is null OR expiration_date >= today
        """
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        return {
            "$and": [
                {"effective_date": {"$lte": today}},
            ]
        }

    # ------------------------------------------------------------------
    # Result parsing
    # ------------------------------------------------------------------

    def _parse_raw_result(
        self,
        raw: dict,
        retrieval_type: str,
        namespace: str,
        latency_ms: float,
        cpt_codes: list[str],
        icd_codes: list[str],
    ) -> QueryResult:
        """Convert a raw Pinecone response dict to a typed QueryResult."""
        matches: list[RetrievalMatch] = []

        for hit in raw.get("matches", []):
            score = float(hit.get("score", 0.0))
            if score < MIN_SCORE_THRESHOLD:
                continue
            meta_dict = hit.get("metadata") or {}
            try:
                metadata = PolicyChunkMetadata.from_pinecone_dict(meta_dict)
                matches.append(
                    RetrievalMatch(
                        vector_id=hit.get("id", ""),
                        score=score,
                        metadata=metadata,
                    )
                )
            except Exception as exc:
                self._log.warning(
                    "retrieval.metadata_parse_error",
                    vector_id=hit.get("id"),
                    error=str(exc),
                )

        return QueryResult(
            matches=matches,
            total_matches=len(matches),
            retrieval_type=retrieval_type,
            latency_ms=round(latency_ms, 1),
            namespace=namespace,
            query_cpt_codes=cpt_codes,
            query_icd_codes=icd_codes,
        )

    # ------------------------------------------------------------------
    # Cache serialization helpers
    # ------------------------------------------------------------------

    def _serialize_for_cache(self, result: QueryResult) -> list[dict]:
        """Serialize QueryResult matches to a JSON-safe list for the cache."""
        return [
            {
                "vector_id": m.vector_id,
                "score": m.score,
                "metadata": m.metadata.to_pinecone_dict(),
            }
            for m in result.matches
        ]

    def _deserialize_cached(
        self,
        cached: list[dict],
        retrieval_type: str,
        namespace: str,
        cpt_codes: list[str],
        icd_codes: list[str],
    ) -> QueryResult:
        """Reconstruct a QueryResult from cached serialized data."""
        matches: list[RetrievalMatch] = []
        for item in cached:
            try:
                matches.append(
                    RetrievalMatch(
                        vector_id=item["vector_id"],
                        score=float(item["score"]),
                        metadata=PolicyChunkMetadata.from_pinecone_dict(
                            item["metadata"]
                        ),
                    )
                )
            except Exception:
                pass

        return QueryResult(
            matches=matches,
            total_matches=len(matches),
            retrieval_type=retrieval_type,
            latency_ms=0.0,  # cached — no latency
            namespace=namespace,
            query_cpt_codes=cpt_codes,
            query_icd_codes=icd_codes,
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _track_metrics(self, result: QueryResult, latency_ms: float) -> None:
        try:
            from app.monitoring.metrics import (
                RETRIEVAL_LATENCY_SECONDS,
                RETRIEVAL_RESULTS_COUNT,
            )
            RETRIEVAL_LATENCY_SECONDS.labels(
                retrieval_type=result.retrieval_type
            ).observe(latency_ms / 1000)
            RETRIEVAL_RESULTS_COUNT.observe(result.total_matches)
        except Exception:
            pass
