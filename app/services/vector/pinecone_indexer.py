"""Policy vector indexing operations for Pinecone."""

from __future__ import annotations

from dataclasses import dataclass

import anyio

from app.services.vector.pinecone_client import ensure_pinecone_index, get_pinecone_index


@dataclass(frozen=True)
class UpsertResult:
    upserted: int


class PineconePolicyIndexer:
    async def upsert(
        self,
        *,
        namespace: str,
        ids: list[str],
        vectors: list[list[float]],
        metadatas: list[dict],
        batch_size: int = 100,
    ) -> UpsertResult:
        if len(ids) != len(vectors) or len(ids) != len(metadatas):
            raise ValueError("ids/vectors/metadatas length mismatch")

        def _upsert_sync() -> int:
            # ensure_pinecone_index runs inside the thread — safe for sync Pinecone SDK calls
            ensure_pinecone_index()
            index = get_pinecone_index()
            upserted = 0
            for i in range(0, len(ids), batch_size):
                batch = [
                    {"id": ids[j], "values": vectors[j], "metadata": metadatas[j]}
                    for j in range(i, min(i + batch_size, len(ids)))
                ]
                res = index.upsert(vectors=batch, namespace=namespace)
                upserted += int(getattr(res, "upserted_count", len(batch)))
            return upserted

        upserted = await anyio.to_thread.run_sync(_upsert_sync)
        return UpsertResult(upserted=upserted)

    async def delete_by_ids(self, *, namespace: str, ids: list[str], batch_size: int = 1000) -> int:
        if not ids:
            return 0

        def _delete_sync() -> int:
            index = get_pinecone_index()
            deleted = 0
            for i in range(0, len(ids), batch_size):
                batch_ids = ids[i : i + batch_size]
                index.delete(ids=batch_ids, namespace=namespace)
                deleted += len(batch_ids)
            return deleted

        return await anyio.to_thread.run_sync(_delete_sync)

