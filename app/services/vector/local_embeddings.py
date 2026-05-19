"""Local deterministic embedding service for development/testing.

Generates stable 1536-dim unit vectors from text using SHA-256 hashing.
Vectors are deterministic (same text → same vector) and normalized for
cosine similarity, but are NOT semantically meaningful — suitable for
testing the full pipeline when no cloud embedding provider is configured.

This is ONLY activated as a final fallback; Azure OpenAI takes priority.
"""

from __future__ import annotations

import hashlib
import struct

import structlog

from app.services.vector.embeddings import EmbeddingResult

logger = structlog.get_logger(__name__)

_DIM = 3072  # matches text-embedding-3-large default output dimensions


def _text_to_vector(text: str) -> list[float]:
    """Deterministically hash text into a normalized 1536-dim float vector."""
    import math

    # Use multiple SHA-256 digests to fill 3072 floats (3072 * 4 bytes = 12288 bytes)
    # One SHA-256 = 32 bytes = 8 floats, so we need ceil(3072/8) = 384 digests
    raw_bytes = bytearray()
    seed = text.encode("utf-8", errors="replace")
    for i in range(384):
        h = hashlib.sha256(seed + i.to_bytes(4, "little")).digest()
        raw_bytes.extend(h)

    # Unpack as signed 32-bit ints, convert to floats
    n = _DIM
    ints = struct.unpack_from(f"{n}i", raw_bytes, 0)
    floats = [float(v) for v in ints]

    # L2-normalize so cosine similarity works correctly
    norm = math.sqrt(sum(v * v for v in floats)) or 1.0
    return [v / norm for v in floats]


class LocalEmbeddingService:
    """Hash-based local embeddings — no network calls, no API keys required."""

    async def embed_texts(self, texts: list[str], *, batch_size: int = 64) -> EmbeddingResult:
        logger.warning(
            "local_embeddings.using_hash_fallback",
            text_count=len(texts),
            note="Vectors are NOT semantically meaningful. Configure Azure OpenAI for production use.",
        )
        vectors = [_text_to_vector(t) for t in texts]
        return EmbeddingResult(vectors=vectors)
