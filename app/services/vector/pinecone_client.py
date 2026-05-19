"""Pinecone client helpers (thin wrapper)."""

from __future__ import annotations

import logging
from functools import lru_cache

from pinecone import Pinecone, ServerlessSpec

from app.core.config.settings import get_settings

logger = logging.getLogger(__name__)

# Dimension for text-embedding-3-small / text-embedding-ada-002 (1536-d)
# Change to 3072 if using text-embedding-3-large.
_EMBEDDING_DIMENSION = 1536


@lru_cache(maxsize=1)
def get_pinecone_client() -> Pinecone:
    settings = get_settings()
    if not settings.pinecone_api_key:
        raise RuntimeError("Pinecone not configured (PINECONE_API_KEY missing)")
    return Pinecone(api_key=settings.pinecone_api_key.get_secret_value())


def _parse_environment(env: str) -> tuple[str, str]:
    """
    Parse 'us-east-1-aws' → (cloud='aws', region='us-east-1').
    Handles both 'us-east-1-aws' and 'aws-us-east-1' formats.
    Falls back to ('aws', 'us-east-1') if unparseable.
    """
    parts = env.split("-")
    # Last token is the cloud provider: us-east-1-aws → aws
    if parts and parts[-1] in ("aws", "gcp", "azure"):
        cloud = parts[-1]
        region = "-".join(parts[:-1])
        return cloud, region
    # Try first token: aws-us-east-1 → aws
    if parts and parts[0] in ("aws", "gcp", "azure"):
        cloud = parts[0]
        region = "-".join(parts[1:])
        return cloud, region
    return "aws", "us-east-1"


def ensure_pinecone_index() -> None:
    """
    Create the Pinecone index if it does not already exist.
    Uses serverless spec derived from PINECONE_ENVIRONMENT.
    Safe to call multiple times (no-op if index already exists).
    """
    settings = get_settings()
    client = get_pinecone_client()
    index_name = settings.pinecone_index_name

    existing = {idx.name for idx in client.list_indexes()}
    if index_name in existing:
        return

    cloud, region = _parse_environment(settings.pinecone_environment)
    logger.info(
        "pinecone: creating index '%s' (dim=%d, cloud=%s, region=%s)",
        index_name, _EMBEDDING_DIMENSION, cloud, region,
    )
    client.create_index(
        name=index_name,
        dimension=_EMBEDDING_DIMENSION,
        metric="cosine",
        spec=ServerlessSpec(cloud=cloud, region=region),
    )
    logger.info("pinecone: index '%s' created", index_name)


def get_pinecone_index():
    """Return the Pinecone index client (does NOT auto-create the index).
    Call ensure_pinecone_index() first if you need auto-creation."""
    settings = get_settings()
    client = get_pinecone_client()
    return client.Index(settings.pinecone_index_name)

