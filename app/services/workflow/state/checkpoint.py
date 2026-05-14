"""
Redis-backed async LangGraph checkpointer.

Stores workflow checkpoints in Redis so that:
  - Interrupted workflows resume from their last saved state.
  - The full checkpoint history for a case is retrievable for audit.
  - Multiple replicas can share state (Redis as shared coordination layer).

Key design:
  - Async-first: all Redis operations use aioredis (redis-py async API).
  - Serialization: pickle for full Python fidelity (Pydantic models, enums, etc.)
    Swap for msgpack/orjson + type-tag registry if untrusted deserialization is
    a concern in your threat model.
  - TTL: 7 days default — configurable via WORKFLOW_CHECKPOINT_TTL_DAYS env var.
  - Key layout:
      Checkpoint data:   pa:v1:wf:ckpt:{thread_id}:{ns}:{checkpoint_id}  → bytes
      Sorted index:      pa:v1:wf:ckpt:idx:{thread_id}:{ns}              → sorted set
                         (score = UNIX timestamp, member = checkpoint_id)
  - Sync stubs (get_tuple, list, put) raise NotImplementedError — this
    checkpointer is designed for async FastAPI environments only.

LangGraph compatibility: langgraph ^0.1.x
"""

from __future__ import annotations

import logging
import pickle
import time
from typing import Any, AsyncIterator, Iterator, Optional

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from redis.asyncio import Redis

logger = structlog.get_logger(__name__)

_KEY_PREFIX        = "pa:v1:wf:ckpt"
_DEFAULT_TTL_SECS  = 7 * 24 * 3600    # 7 days
_DEFAULT_NS        = ""                 # LangGraph default namespace


def _data_key(thread_id: str, ns: str, checkpoint_id: str) -> str:
    """Key that stores a single checkpoint's raw bytes."""
    return f"{_KEY_PREFIX}:{thread_id}:{ns}:{checkpoint_id}"


def _index_key(thread_id: str, ns: str) -> str:
    """Sorted-set key that indexes checkpoint IDs by insertion timestamp."""
    return f"{_KEY_PREFIX}:idx:{thread_id}:{ns}"


def _config_ns(config: RunnableConfig) -> str:
    return (config.get("configurable") or {}).get("checkpoint_ns", _DEFAULT_NS)


def _config_thread_id(config: RunnableConfig) -> str:
    return (config.get("configurable") or {}).get("thread_id", "")


def _config_checkpoint_id(config: RunnableConfig) -> str | None:
    return (config.get("configurable") or {}).get("thread_ts")  # LangGraph convention


class AsyncRedisSaver(BaseCheckpointSaver):
    """
    Async Redis checkpointer for LangGraph PA workflows.

    Usage:
        redis = Redis.from_url("redis://localhost:6379/0")
        saver = AsyncRedisSaver(redis, ttl=7 * 24 * 3600)

        graph = StateGraph(PAWorkflowState)
        ...
        compiled = graph.compile(checkpointer=saver)
        await compiled.ainvoke(state, config={"configurable": {"thread_id": case_id}})

    Or use the factory:
        saver = AsyncRedisSaver.from_settings()
    """

    def __init__(
        self,
        redis: Redis,
        *,
        ttl: int = _DEFAULT_TTL_SECS,
    ) -> None:
        super().__init__()
        self._redis = redis
        self._ttl   = ttl

    # ------------------------------------------------------------------
    # Async implementation (primary path for FastAPI)
    # ------------------------------------------------------------------

    async def aget_tuple(
        self,
        config: RunnableConfig,
    ) -> Optional[CheckpointTuple]:
        """
        Retrieve the most recent checkpoint (or a specific one) for a thread.

        If config["configurable"]["thread_ts"] is set, fetches that specific
        checkpoint; otherwise returns the latest one.
        """
        thread_id     = _config_thread_id(config)
        ns            = _config_ns(config)
        checkpoint_id = _config_checkpoint_id(config)

        if not thread_id:
            return None

        try:
            if checkpoint_id:
                # Fetch specific checkpoint by ID
                raw = await self._redis.get(_data_key(thread_id, ns, checkpoint_id))
                if not raw:
                    return None
                return self._deserialize_tuple(raw, config)

            # Fetch latest: highest-score member from the sorted index
            idx_key = _index_key(thread_id, ns)
            members = await self._redis.zrange(idx_key, -1, -1, withscores=False)
            if not members:
                return None

            latest_id = members[0].decode() if isinstance(members[0], bytes) else members[0]
            raw = await self._redis.get(_data_key(thread_id, ns, latest_id))
            if not raw:
                return None

            return self._deserialize_tuple(raw, config)

        except Exception as exc:
            logger.warning(
                "checkpoint.redis.get_failed",
                thread_id=thread_id,
                error=str(exc),
            )
            return None

    async def aget(self, config: RunnableConfig) -> Optional[Checkpoint]:
        """Return just the Checkpoint (no metadata/parent)."""
        result = await self.aget_tuple(config)
        return result.checkpoint if result else None

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
    ) -> RunnableConfig:
        """
        Persist a checkpoint and return an updated config pointing to it.

        Steps:
          1. Serialize (checkpoint + metadata + parent_config) with pickle.
          2. Store bytes under the data key with TTL.
          3. Add checkpoint_id to the sorted index (score = timestamp).
          4. Refresh TTL on the index key.
        """
        thread_id     = _config_thread_id(config)
        ns            = _config_ns(config)
        checkpoint_id = checkpoint["id"]

        payload = {
            "checkpoint":    checkpoint,
            "metadata":      metadata,
            "parent_config": config,
        }
        raw = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)

        data_key = _data_key(thread_id, ns, checkpoint_id)
        idx_key  = _index_key(thread_id, ns)
        score    = time.time()

        try:
            pipe = self._redis.pipeline(transaction=True)
            pipe.set(data_key, raw, ex=self._ttl)
            pipe.zadd(idx_key, {checkpoint_id: score})
            pipe.expire(idx_key, self._ttl)
            await pipe.execute()

            logger.debug(
                "checkpoint.redis.saved",
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
                step=metadata.get("step", -1),
            )
        except Exception as exc:
            logger.error(
                "checkpoint.redis.put_failed",
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
                error=str(exc),
            )
            raise

        return {
            **config,
            "configurable": {
                **(config.get("configurable") or {}),
                "thread_ts": checkpoint_id,
            },
        }

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """
        Yield all checkpoints for a thread in reverse-chronological order.

        Args:
            config: Thread configuration (must contain thread_id).
            filter: Not supported — ignored (future extension).
            before: Only return checkpoints older than this config's checkpoint.
            limit:  Maximum number of results.
        """
        if not config:
            return

        thread_id = _config_thread_id(config)
        ns        = _config_ns(config)
        if not thread_id:
            return

        idx_key = _index_key(thread_id, ns)

        try:
            # Get all checkpoint IDs sorted newest-first
            members = await self._redis.zrange(idx_key, 0, -1, withscores=True, rev=True)
        except Exception as exc:
            logger.warning("checkpoint.redis.list_failed", thread_id=thread_id, error=str(exc))
            return

        before_ts: float | None = None
        if before:
            before_id = _config_checkpoint_id(before)
            if before_id:
                score = await self._redis.zscore(idx_key, before_id)
                before_ts = float(score) if score else None

        emitted = 0
        for member, score in members:
            checkpoint_id = member.decode() if isinstance(member, bytes) else member

            # Apply before filter
            if before_ts is not None and float(score) >= before_ts:
                continue

            raw = await self._redis.get(_data_key(thread_id, ns, checkpoint_id))
            if not raw:
                continue

            try:
                tup = self._deserialize_tuple(raw, config)
            except Exception:
                continue

            yield tup
            emitted += 1
            if limit and emitted >= limit:
                break

    # ------------------------------------------------------------------
    # Sync stubs — not supported in async-only environment
    # ------------------------------------------------------------------

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        raise NotImplementedError(
            "AsyncRedisSaver is async-only. Use aget_tuple() in an async context."
        )

    def list(
        self,
        config: Optional[RunnableConfig],
        **kwargs: Any,
    ) -> Iterator[CheckpointTuple]:
        raise NotImplementedError(
            "AsyncRedisSaver is async-only. Use alist() in an async context."
        )

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
    ) -> RunnableConfig:
        raise NotImplementedError(
            "AsyncRedisSaver is async-only. Use aput() in an async context."
        )

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def adelete_thread(self, thread_id: str, ns: str = _DEFAULT_NS) -> int:
        """
        Delete all checkpoints for a thread (e.g., after case archival).

        Returns the number of checkpoint records deleted.
        """
        idx_key = _index_key(thread_id, ns)
        members = await self._redis.zrange(idx_key, 0, -1)
        if not members:
            return 0

        keys = [_data_key(thread_id, ns, m.decode() if isinstance(m, bytes) else m) for m in members]
        keys.append(idx_key)

        deleted = await self._redis.delete(*keys)
        logger.info("checkpoint.redis.thread_deleted", thread_id=thread_id, keys_deleted=deleted)
        return deleted

    async def acount(self, thread_id: str, ns: str = _DEFAULT_NS) -> int:
        """Number of saved checkpoints for a thread."""
        idx_key = _index_key(thread_id, ns)
        return await self._redis.zcard(idx_key)

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _deserialize_tuple(
        raw: bytes,
        config: RunnableConfig,
    ) -> CheckpointTuple:
        payload = pickle.loads(raw)
        return CheckpointTuple(
            config=config,
            checkpoint=payload["checkpoint"],
            metadata=payload.get("metadata"),
            parent_config=payload.get("parent_config"),
        )

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls) -> "AsyncRedisSaver":
        """
        Construct from application settings.

        Reads REDIS_URL and WORKFLOW_CHECKPOINT_TTL_DAYS from settings.
        The Redis connection is created but NOT connected here — the connection
        pool is initialised lazily on the first command.
        """
        from app.core.config.settings import get_settings

        settings = get_settings()
        redis = Redis.from_url(
            str(settings.redis_url),
            encoding="utf-8",
            decode_responses=False,  # We store raw bytes (pickle)
        )
        ttl_days = getattr(settings, "workflow_checkpoint_ttl_days", 7)
        return cls(redis, ttl=int(ttl_days) * 24 * 3600)

    @classmethod
    def from_redis(cls, redis: Redis, ttl: int = _DEFAULT_TTL_SECS) -> "AsyncRedisSaver":
        """Construct from an existing Redis client (useful in tests)."""
        return cls(redis, ttl=ttl)
