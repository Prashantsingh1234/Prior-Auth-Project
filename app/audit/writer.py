"""
Async audit writer — non-blocking, queue-backed, batch-flushing.

Architecture:
  ┌────────────────────────────────────────────────────────────────┐
  │  Hot path (request/service code)                               │
  │    audit_writer.emit(record)  ──→  asyncio.Queue  ──→  ...    │
  │    Returns immediately (put_nowait)                            │
  └──────────────────────────────┬─────────────────────────────────┘
                                 │  background task
                                 ▼
  ┌─────────────────────────────────────────────────────────────── ┐
  │  Worker loop                                                    │
  │    • Drain up to BATCH_SIZE records per cycle                  │
  │    • Wait up to BATCH_WAIT_SECS for a full batch               │
  │    • Write batch to all storage backends                       │
  │    • If queue > OVERFLOW_WARN_THRESHOLD, warn once per minute  │
  └─────────────────────────────────────────────────────────────── ┘

Emergency fallback:
  If the queue is full (system overload, DB outage), records are emitted
  synchronously via StructlogAuditStorage so they appear in log aggregators
  even if the DB write is delayed or lost.  The emission is logged with
  severity WARNING to trigger alerting.

Lifecycle:
  await writer.start()       — called in lifespan startup
  await writer.stop(drain_timeout=30.0) — called in lifespan shutdown

  The stop() method:
    1. Sets _stopping flag
    2. Waits up to drain_timeout for the queue to drain
    3. Flushes whatever remains
    4. Cancels the worker task
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from app.audit.models import AuditRecord
from app.audit.storage import AuditStorageBackend, CompositeAuditStorage, StructlogAuditStorage

logger = structlog.get_logger(__name__)

# Queue capacity — 10,000 records gives ~5–10 seconds headroom at high load
QUEUE_MAX_SIZE = 10_000

# Batch tuning
BATCH_SIZE = 50           # Max records per DB transaction
BATCH_WAIT_SECS = 1.0    # Max seconds to wait for a full batch

# Warn once per minute when queue depth exceeds this fraction of QUEUE_MAX_SIZE
OVERFLOW_WARN_THRESHOLD = 0.80


class AuditWriter:
    """
    Non-blocking, queue-backed audit writer.

    One instance per application process — create via AuditWriter.default().
    """

    def __init__(self, storage: AuditStorageBackend) -> None:
        self._storage = storage
        self._queue: asyncio.Queue[AuditRecord] = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
        self._worker_task: asyncio.Task | None = None
        self._stopping = False
        self._fallback_log = StructlogAuditStorage()
        self._last_overflow_warn_ts: float = 0.0
        self._total_emitted: int = 0
        self._total_dropped: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background worker.  Call once at application startup."""
        if self._worker_task is not None and not self._worker_task.done():
            return
        self._stopping = False
        self._worker_task = asyncio.create_task(
            self._worker_loop(), name="audit_writer_worker"
        )
        logger.info("audit.writer.started", queue_max=QUEUE_MAX_SIZE, batch_size=BATCH_SIZE)

    async def stop(self, drain_timeout: float = 30.0) -> None:
        """
        Gracefully stop the writer.

        Waits up to drain_timeout seconds for the queue to drain, then
        flushes any remaining items before cancelling the worker task.
        """
        if self._worker_task is None:
            return
        self._stopping = True
        logger.info(
            "audit.writer.stopping",
            queue_depth=self._queue.qsize(),
            drain_timeout=drain_timeout,
        )

        try:
            await asyncio.wait_for(self._queue.join(), timeout=drain_timeout)
        except asyncio.TimeoutError:
            remaining = self._queue.qsize()
            logger.warning(
                "audit.writer.drain_timeout",
                remaining=remaining,
                drain_timeout=drain_timeout,
            )
            await self._flush_remaining()

        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        await self._storage.close()
        logger.info(
            "audit.writer.stopped",
            total_emitted=self._total_emitted,
            total_dropped=self._total_dropped,
        )

    def emit(self, record: AuditRecord) -> None:
        """
        Enqueue an audit record for async writing.

        Non-blocking (put_nowait).  If the queue is full, the record is
        written synchronously via the structlog fallback and a warning is
        emitted — the record is never silently dropped.
        """
        try:
            self._queue.put_nowait(record)
            self._total_emitted += 1
            self._maybe_warn_overflow()
        except asyncio.QueueFull:
            self._total_dropped += 1
            logger.error(
                "audit.writer.queue_full",
                event_id=record.event_id,
                category=record.category.value,
                total_dropped=self._total_dropped,
            )
            # Emergency structlog write — at least gets into log aggregator
            asyncio.get_event_loop().create_task(
                self._emergency_log(record)
            )

    async def emit_async(self, record: AuditRecord) -> None:
        """
        Async version — waits if the queue is full (up to 5 seconds).

        Use this in contexts where blocking is acceptable (e.g., shutdown).
        """
        try:
            await asyncio.wait_for(self._queue.put(record), timeout=5.0)
            self._total_emitted += 1
        except (asyncio.TimeoutError, asyncio.QueueFull):
            await self._emergency_log(record)

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    @property
    def is_healthy(self) -> bool:
        """True when the worker task is running and queue isn't overloaded."""
        if self._worker_task is None or self._worker_task.done():
            return False
        return self._queue.qsize() < int(QUEUE_MAX_SIZE * OVERFLOW_WARN_THRESHOLD)

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    async def _worker_loop(self) -> None:
        logger.debug("audit.writer.worker.running")
        while not self._stopping or not self._queue.empty():
            try:
                batch = await self._collect_batch()
                if batch:
                    await self._write_batch(batch)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    "audit.writer.worker.error",
                    error=str(exc),
                    exc_info=True,
                )
                await asyncio.sleep(1)  # brief back-off on unexpected error

    async def _collect_batch(self) -> list[AuditRecord]:
        """
        Collect up to BATCH_SIZE records, waiting at most BATCH_WAIT_SECS.
        """
        batch: list[AuditRecord] = []
        deadline = asyncio.get_event_loop().time() + BATCH_WAIT_SECS

        while len(batch) < BATCH_SIZE:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                record = await asyncio.wait_for(
                    self._queue.get(), timeout=max(0.05, remaining)
                )
                batch.append(record)
            except asyncio.TimeoutError:
                break

        return batch

    async def _write_batch(self, batch: list[AuditRecord]) -> None:
        t0 = time.monotonic()
        try:
            await self._storage.write_batch(batch)
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.debug(
                "audit.writer.batch_flushed",
                count=len(batch),
                elapsed_ms=round(elapsed_ms, 1),
            )
        except Exception as exc:
            logger.error(
                "audit.writer.batch_flush_failed",
                count=len(batch),
                error=str(exc),
            )
        finally:
            for _ in batch:
                try:
                    self._queue.task_done()
                except ValueError:
                    pass

    async def _flush_remaining(self) -> None:
        """Drain and write all remaining queue items (used during shutdown)."""
        remaining: list[AuditRecord] = []
        while not self._queue.empty():
            try:
                remaining.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if remaining:
            logger.info("audit.writer.flushing_remaining", count=len(remaining))
            await self._write_batch(remaining)

    async def _emergency_log(self, record: AuditRecord) -> None:
        """Last-resort: emit to structlog when DB write is impossible."""
        try:
            await self._fallback_log.write(record)
        except Exception:
            pass

    def _maybe_warn_overflow(self) -> None:
        threshold = int(QUEUE_MAX_SIZE * OVERFLOW_WARN_THRESHOLD)
        if self._queue.qsize() >= threshold:
            now = time.monotonic()
            if now - self._last_overflow_warn_ts > 60:
                logger.warning(
                    "audit.writer.queue_near_full",
                    depth=self._queue.qsize(),
                    max=QUEUE_MAX_SIZE,
                )
                self._last_overflow_warn_ts = now

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def default(cls) -> "AuditWriter":
        """Create the default writer with DB + structlog storage."""
        return cls(storage=CompositeAuditStorage.default())

    @classmethod
    def log_only(cls) -> "AuditWriter":
        """Create a log-only writer (no DB — useful for testing)."""
        return cls(storage=StructlogAuditStorage())


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_writer_instance: AuditWriter | None = None


def get_audit_writer() -> AuditWriter:
    """
    Return the module-level AuditWriter singleton.

    Must be started before first use (call await writer.start() in lifespan).
    """
    global _writer_instance
    if _writer_instance is None:
        _writer_instance = AuditWriter.default()
    return _writer_instance


def emit(record: AuditRecord) -> None:
    """
    Module-level convenience function: emit a record via the singleton writer.

    Safe to call from any context — never raises.
    """
    try:
        get_audit_writer().emit(record)
    except Exception as exc:
        logger.error("audit.emit.failed", error=str(exc))
