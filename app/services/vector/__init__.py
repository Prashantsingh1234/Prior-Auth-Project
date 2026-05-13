"""
Vector database package — Pinecone integration for policy retrieval.

Primary entry points:

    from app.services.vector import (
        PineconeClient, get_pinecone_client, init_pinecone, close_pinecone,
        EmbeddingService,
        RetrievalService,
        VectorUpsertService,
        PolicyIndexer,
    )

Lifecycle (called from app/main.py lifespan):
    await init_pinecone()   # startup
    await close_pinecone()  # shutdown

Typical service-layer usage:
    client = get_pinecone_client()
    embedding = EmbeddingService.from_settings()
    retrieval = RetrievalService(client, embedding)
    result = await retrieval.hybrid_search(query, cpt_codes, icd_codes)
"""

from app.services.vector.embeddings import EmbeddingService, EmbeddingError
from app.services.vector.indexer import PolicyIndexer
from app.services.vector.pinecone_client import (
    PineconeClient,
    VectorStoreError,
    close_pinecone,
    get_pinecone_client,
    get_pinecone_health,
    init_pinecone,
)
from app.services.vector.retrieval import RetrievalService
from app.services.vector.schemas import (
    IndexStats,
    PolicyChunkMetadata,
    PolicyVector,
    QueryResult,
    RetrievalMatch,
    SparseVector,
)
from app.services.vector.sparse import (
    build_medical_sparse_vector,
    build_query_sparse_vector,
)
from app.services.vector.upsert import VectorUpsertService

__all__ = [
    # Client lifecycle
    "PineconeClient",
    "VectorStoreError",
    "init_pinecone",
    "close_pinecone",
    "get_pinecone_client",
    "get_pinecone_health",
    # Services
    "EmbeddingService",
    "EmbeddingError",
    "RetrievalService",
    "VectorUpsertService",
    "PolicyIndexer",
    # Schemas
    "PolicyChunkMetadata",
    "PolicyVector",
    "QueryResult",
    "RetrievalMatch",
    "SparseVector",
    "IndexStats",
    # Sparse utilities
    "build_medical_sparse_vector",
    "build_query_sparse_vector",
]
