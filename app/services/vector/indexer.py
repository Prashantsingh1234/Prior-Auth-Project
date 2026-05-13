"""
Policy document indexer — end-to-end pipeline.

Takes a raw policy document (text + metadata) and produces Pinecone vectors:
    1. Clean + normalize text
    2. Chunk into overlapping segments
    3. Generate dense embeddings (with cache)
    4. Generate sparse vectors (medical code BM25)
    5. Upsert to Pinecone in batches

Chunking strategy:
  Sentence-aware chunking at ~512-token boundaries with 50-token overlap.
  Overlap ensures that a policy criterion spanning a chunk boundary is
  captured in at least one complete chunk.

Reindexing strategy:
  Call reindex_policy() to atomically replace stale vectors.
  The upsert service inserts new vectors before deleting old ones to
  ensure continuous coverage during the transition.
"""

from __future__ import annotations

import re
import structlog

from app.services.vector.embeddings import EmbeddingService
from app.services.vector.schemas import PolicyChunkMetadata, PolicyVector, SparseVector
from app.services.vector.sparse import build_medical_sparse_vector
from app.services.vector.upsert import VectorUpsertService

logger = structlog.get_logger(__name__)

# Approximate characters per token (conservative estimate for medical text)
_CHARS_PER_TOKEN = 3.5

# Chunk target size in approximate tokens
DEFAULT_CHUNK_TOKENS = 512

# Overlap in approximate tokens
DEFAULT_OVERLAP_TOKENS = 50


class PolicyIndexer:
    """
    Orchestrates the policy document → Pinecone vector pipeline.

    Usage:
        indexer = PolicyIndexer(embedding_service, upsert_service)
        chunks_indexed = await indexer.index_policy(
            policy_text="...",
            metadata=PolicyChunkMetadata(
                policy_id="aetna-cgm-v3",
                policy_name="CGM Coverage Criteria",
                ...
            ),
        )
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        upsert_service: VectorUpsertService,
    ) -> None:
        self._embedding = embedding_service
        self._upsert = upsert_service
        self._log = structlog.get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Main indexing entry points
    # ------------------------------------------------------------------

    async def index_policy(
        self,
        policy_text: str,
        metadata: PolicyChunkMetadata,
        namespace: str | None = None,
        chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
        overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    ) -> int:
        """
        Index a complete policy document.

        Args:
            policy_text:   Full text of the policy document
            metadata:      Policy metadata (id, version, codes, etc.)
                           chunk_index and total_chunks are auto-filled.
            namespace:     Pinecone namespace override
            chunk_tokens:  Target chunk size in ~tokens
            overlap_tokens: Overlap between adjacent chunks

        Returns:
            Number of chunks indexed.
        """
        self._log.info(
            "indexer.started",
            policy_id=metadata.policy_id,
            version=metadata.policy_version,
            text_length=len(policy_text),
        )

        chunks = self._chunk_text(policy_text, chunk_tokens, overlap_tokens)
        if not chunks:
            self._log.warning("indexer.no_chunks", policy_id=metadata.policy_id)
            return 0

        total = len(chunks)
        self._log.info("indexer.chunked", policy_id=metadata.policy_id, chunks=total)

        # Batch-generate all embeddings in one API call
        embeddings = await self._embedding.embed_batch(chunks)

        # Build PolicyVector objects
        vectors: list[PolicyVector] = []
        all_codes = metadata.cpt_codes + metadata.icd_codes

        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            sparse = build_medical_sparse_vector(chunk_text, all_codes)
            chunk_meta = metadata.model_copy(
                update={
                    "chunk_index": i,
                    "total_chunks": total,
                    "chunk_text": chunk_text[:1000],
                }
            )
            vectors.append(
                PolicyVector(
                    id=PolicyVector.make_id(metadata.policy_id, i),
                    values=embedding,
                    sparse_values=sparse,
                    metadata=chunk_meta,
                )
            )

        upserted = await self._upsert.upsert_policy_chunks(vectors, namespace)

        self._log.info(
            "indexer.complete",
            policy_id=metadata.policy_id,
            chunks_indexed=upserted,
        )
        return upserted

    async def reindex_policy(
        self,
        policy_text: str,
        metadata: PolicyChunkMetadata,
        namespace: str | None = None,
    ) -> dict[str, int]:
        """
        Replace an existing policy version with a freshly-indexed one.

        Safe to call for both new policies (no-op delete) and updates.
        Returns {"upserted": N, "deleted_filter_applied": 1}.
        """
        chunks = self._chunk_text(policy_text)
        total = len(chunks)
        all_codes = metadata.cpt_codes + metadata.icd_codes
        embeddings = await self._embedding.embed_batch(chunks)

        vectors: list[PolicyVector] = []
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            sparse = build_medical_sparse_vector(chunk_text, all_codes)
            chunk_meta = metadata.model_copy(
                update={"chunk_index": i, "total_chunks": total, "chunk_text": chunk_text[:1000]}
            )
            vectors.append(
                PolicyVector(
                    id=PolicyVector.make_id(metadata.policy_id, i),
                    values=embedding,
                    sparse_values=sparse,
                    metadata=chunk_meta,
                )
            )

        return await self._upsert.replace_policy_version(
            policy_id=metadata.policy_id,
            new_vectors=vectors,
            namespace=namespace,
        )

    async def delete_policy(
        self,
        policy_id: str,
        namespace: str | None = None,
    ) -> None:
        """Remove all chunks for a retired or expired policy."""
        await self._upsert.delete_policy(policy_id, namespace)
        self._log.info("indexer.policy_deleted", policy_id=policy_id)

    # ------------------------------------------------------------------
    # Text chunking
    # ------------------------------------------------------------------

    def _chunk_text(
        self,
        text: str,
        chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
        overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    ) -> list[str]:
        """
        Split text into overlapping chunks at sentence boundaries.

        Strategy:
        1. Split into sentences using punctuation heuristics
        2. Accumulate sentences until chunk_size is reached
        3. Include the last `overlap` characters of the previous chunk
           at the start of the next chunk

        Returns:
            List of text chunks (each ≤ chunk_tokens * chars_per_token chars).
        """
        text = self._clean_text(text)
        if not text:
            return []

        max_chars = int(chunk_tokens * _CHARS_PER_TOKEN)
        overlap_chars = int(overlap_tokens * _CHARS_PER_TOKEN)

        sentences = self._split_sentences(text)
        if not sentences:
            return []

        chunks: list[str] = []
        current_chunk: list[str] = []
        current_len = 0
        overlap_text = ""

        for sentence in sentences:
            sentence_len = len(sentence)

            if current_len + sentence_len > max_chars and current_chunk:
                chunk = overlap_text + " ".join(current_chunk)
                chunks.append(chunk.strip())
                # Compute overlap for next chunk
                overlap_text = self._compute_overlap(
                    " ".join(current_chunk), overlap_chars
                )
                current_chunk = []
                current_len = 0

            current_chunk.append(sentence)
            current_len += sentence_len

        # Flush remaining text
        if current_chunk:
            chunks.append((overlap_text + " ".join(current_chunk)).strip())

        # Guard: if text was very short, return it as a single chunk
        if not chunks and text.strip():
            chunks = [text.strip()[:max_chars]]

        return [c for c in chunks if len(c) >= 50]

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """
        Split text into sentences at punctuation boundaries.

        Medical text often has bullet points and numbered lists, so we split
        on sentence-ending punctuation AND list item patterns.
        """
        pattern = r"(?<=[.!?])\s+|(?<=\n)\s*(?=\d+\.\s)|(?<=\n)\s*(?=•\s)"
        parts = re.split(pattern, text)
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def _compute_overlap(text: str, overlap_chars: int) -> str:
        """Return the last `overlap_chars` characters of text as an overlap prefix."""
        if len(text) <= overlap_chars:
            return text + " "
        return text[-overlap_chars:].strip() + " "

    @staticmethod
    def _clean_text(text: str) -> str:
        """Normalize whitespace and remove control characters."""
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
