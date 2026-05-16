"""
Base consumer with ack/nack, retry, and DLQ routing.

Retry protocol
--------------
Every message carries an ``x-pa-retry-count`` header (int, default 0).

On worker exception:
  1. Increment retry_count.
  2. If retry_count <= max_retries:
       - Publish to ``pa.retry`` exchange with routing_key = delay_ms
       - The retry queue's TTL expires → message re-enters the main exchange
         with the original routing key (set via ``x-death`` + per-message header)
       - nack the original message (requeue=False)
  3. If retry_count > max_retries:
       - Publish directly to the DLQ via the DLX exchange
       - nack the original message (requeue=False)
       - Emit DLQ metric

Workers subclass BaseConsumer and implement ``process(task)``.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any

import aio_pika
import structlog
from aio_pika import IncomingMessage, Message
from aio_pika.abc import AbstractIncomingMessage

from app.core.config.settings import get_settings
from app.queues.connection import get_connection
from app.queues.metrics import QUEUE_METRICS
from app.queues.models import AnyTask, TaskMessage, deserialize_task
from app.queues.topology import (
    DLX,
    MAIN_EXCHANGE,
    RETRY_DELAYS_MS,
    RETRY_EXCHANGE,
    QUEUE_SPECS,
    QueueSpec,
)

logger = structlog.get_logger(__name__)


class BaseConsumer(ABC):
    """
    Abstract base for all task consumers.

    Subclasses must implement:
      - queue_spec: QueueSpec — which queue to consume
      - process(task: AnyTask) -> None — business logic

    The framework handles:
      - Prefetch / QoS
      - Deserialization
      - Ack on success
      - Retry with backoff on failure
      - DLQ routing after max retries
      - Prometheus metrics
      - Structured logging with task_id context
    """

    queue_spec: QueueSpec  # defined in subclass

    def __init__(self) -> None:
        settings = get_settings()
        self._max_retries    = settings.worker_max_retries
        self._prefetch       = settings.rabbitmq_prefetch_count
        self._channel: aio_pika.Channel | None = None
        self._queue:   aio_pika.Queue   | None = None
        self._log = structlog.get_logger(self.__class__.__name__)
        self._running = False

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def process(self, task: AnyTask) -> None:
        """
        Execute the task.  Raise any exception to trigger retry/DLQ logic.
        Do NOT call ack/nack — the framework handles that.
        """
        ...

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Open channel, set QoS, and start consuming."""
        self._running = True
        conn    = await get_connection()
        channel = await conn.channel()
        await channel.set_qos(prefetch_count=self._prefetch)
        self._channel = channel

        queue = await channel.get_queue(self.queue_spec.name)
        self._queue = queue

        await queue.consume(self._on_message, no_ack=False)
        self._log.info(
            "consumer.started",
            queue=self.queue_spec.name,
            prefetch=self._prefetch,
            max_retries=self._max_retries,
        )
        QUEUE_METRICS.consumer_count.labels(queue=self.queue_spec.name).inc()

    async def stop(self) -> None:
        """Cancel consumption and close channel."""
        self._running = False
        if self._queue is not None:
            await self._queue.cancel("")  # cancel all consumers on this queue object
        if self._channel is not None and not self._channel.is_closed:
            await self._channel.close()
        QUEUE_METRICS.consumer_count.labels(queue=self.queue_spec.name).dec()
        self._log.info("consumer.stopped", queue=self.queue_spec.name)

    # ------------------------------------------------------------------
    # Message handler (called by aio-pika on each delivery)
    # ------------------------------------------------------------------

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        async with message.process(ignore_processed=True):
            task: AnyTask | None = None
            t0 = time.perf_counter()

            try:
                task = deserialize_task(message.body)
                queue_name = self.queue_spec.name

                QUEUE_METRICS.consumed.labels(
                    queue=queue_name,
                    task_type=task.task_type.value,
                ).inc()

                self._log.info(
                    "consumer.processing",
                    task_id=task.task_id,
                    task_type=task.task_type.value,
                    retry_count=task.retry_count,
                    queue=queue_name,
                )

                await self.process(task)

                elapsed = time.perf_counter() - t0
                QUEUE_METRICS.processing_success.labels(
                    queue=queue_name,
                    task_type=task.task_type.value,
                ).inc()
                QUEUE_METRICS.processing_latency.labels(
                    queue=queue_name,
                    task_type=task.task_type.value,
                ).observe(elapsed)

                self._log.info(
                    "consumer.processed_ok",
                    task_id=task.task_id,
                    task_type=task.task_type.value,
                    elapsed_ms=round(elapsed * 1000, 1),
                )
                # message.process() context manager acks on clean exit

            except Exception as exc:
                elapsed = time.perf_counter() - t0
                retry_count = task.retry_count if task else 0
                queue_name  = self.queue_spec.name
                task_type   = task.task_type.value if task else "unknown"

                self._log.warning(
                    "consumer.processing_failed",
                    task_id=getattr(task, "task_id", "unknown"),
                    task_type=task_type,
                    retry_count=retry_count,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    elapsed_ms=round(elapsed * 1000, 1),
                )
                QUEUE_METRICS.processing_failure.labels(
                    queue=queue_name,
                    task_type=task_type,
                    error_type=type(exc).__name__,
                ).inc()

                if task is not None:
                    await self._handle_failure(message, task, exc)
                else:
                    # Deserialization error — cannot retry; route directly to DLQ
                    await self._route_to_dlq_raw(message)
                # Reject without requeue — our code published retry/DLQ copy
                await message.reject(requeue=False)

    # ------------------------------------------------------------------
    # Retry / DLQ routing
    # ------------------------------------------------------------------

    async def _handle_failure(
        self,
        original: AbstractIncomingMessage,
        task: AnyTask,
        exc: Exception,
    ) -> None:
        next_retry = task.retry_count + 1

        if next_retry <= self._max_retries:
            await self._schedule_retry(task, next_retry)
            QUEUE_METRICS.retried.labels(
                queue=self.queue_spec.name,
                task_type=task.task_type.value,
                retry_number=str(next_retry),
            ).inc()
        else:
            await self._route_to_dlq(task, exc)
            QUEUE_METRICS.dlq_routed.labels(
                queue=self.queue_spec.name,
                task_type=task.task_type.value,
            ).inc()
            self._log.error(
                "consumer.dlq_routed",
                task_id=task.task_id,
                task_type=task.task_type.value,
                retries_exhausted=task.retry_count,
                error=str(exc),
            )

    async def _schedule_retry(self, task: AnyTask, retry_count: int) -> None:
        """Publish task to the TTL-based retry queue for the next delay tier."""
        delay_ms = _retry_delay_ms(retry_count)
        retried_task = task.model_copy(update={"retry_count": retry_count})
        body = retried_task.to_bytes()

        msg = Message(
            body=body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            priority=task.priority,
            content_type="application/json",
            headers={
                "x-task-id":                retried_task.task_id,
                "x-task-type":              retried_task.task_type.value,
                "x-retry-count":            str(retry_count),
                # When TTL expires, aio-pika's DLX re-publishes with this routing key
                "x-pa-original-routing-key": self.queue_spec.routing_key,
            },
            expiration=str(delay_ms),  # per-message TTL (ms) as string
        )

        channel = await self._ensure_channel()
        retry_ex = await channel.get_exchange(RETRY_EXCHANGE)
        await retry_ex.publish(msg, routing_key=str(delay_ms))

        self._log.info(
            "consumer.retry_scheduled",
            task_id=task.task_id,
            retry_count=retry_count,
            delay_ms=delay_ms,
        )

    async def _route_to_dlq(self, task: AnyTask, exc: Exception) -> None:
        """Publish a permanently failed task directly to its DLQ."""
        body = task.to_bytes()
        msg = Message(
            body=body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers={
                "x-task-id":        task.task_id,
                "x-task-type":      task.task_type.value,
                "x-retry-count":    str(task.retry_count),
                "x-failure-reason": str(exc)[:500],
                "x-failure-type":   type(exc).__name__,
            },
        )
        channel = await self._ensure_channel()
        dlx = await channel.get_exchange(DLX)
        await dlx.publish(msg, routing_key=self.queue_spec.dlq_name)

    async def _route_to_dlq_raw(self, original: AbstractIncomingMessage) -> None:
        """Forward an unparseable raw message to DLQ."""
        msg = Message(
            body=original.body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            headers={
                "x-failure-reason": "deserialization_error",
                **dict(original.headers or {}),
            },
        )
        channel = await self._ensure_channel()
        dlx = await channel.get_exchange(DLX)
        await dlx.publish(msg, routing_key=self.queue_spec.dlq_name)

    async def _ensure_channel(self) -> aio_pika.Channel:
        if self._channel is not None and not self._channel.is_closed:
            return self._channel
        conn = await get_connection()
        self._channel = await conn.channel()
        return self._channel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _retry_delay_ms(retry_count: int) -> int:
    """Return the delay bucket (ms) for the given retry attempt (1-indexed)."""
    idx = min(retry_count - 1, len(RETRY_DELAYS_MS) - 1)
    return RETRY_DELAYS_MS[idx]
