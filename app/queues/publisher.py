"""
Async task publisher.

Publishes TaskMessage subclasses to RabbitMQ with:
  - Publisher confirms (guarantees broker receipt before returning)
  - Per-message priority support
  - Automatic channel re-use via a lightweight channel pool
  - Prometheus publish latency + error tracking

Usage:
    from app.queues.publisher import get_publisher

    publisher = await get_publisher()
    await publisher.publish(OCRTask(document_id="...", storage_path="..."))
"""

from __future__ import annotations

import asyncio
import time

import aio_pika
import structlog
from aio_pika import DeliveryMode, Message

from app.queues.connection import get_connection
from app.queues.metrics import QUEUE_METRICS
from app.queues.models import AnyTask, TaskMessage, TaskType
from app.queues.topology import MAIN_EXCHANGE, QUEUE_SPECS

logger = structlog.get_logger(__name__)

# Routing key per task type (matches topology bindings)
_ROUTING_KEYS: dict[TaskType, str] = {
    TaskType.INGESTION:    "ingestion",
    TaskType.OCR:          "ocr",
    TaskType.EMBEDDING:    "embedding",
    TaskType.EVALUATION:   "evaluation",
    TaskType.NOTIFICATION: "notification",
}


class TaskPublisher:
    """
    Publishes tasks to the appropriate RabbitMQ queue.

    One instance is shared per process.  Uses a single channel in confirm
    mode; channel is recreated transparently on failure.
    """

    def __init__(self) -> None:
        self._channel: aio_pika.Channel | None = None
        self._exchange: aio_pika.Exchange | None = None
        self._lock = asyncio.Lock()
        self._log = structlog.get_logger(__name__)

    async def publish(self, task: TaskMessage) -> None:
        """
        Publish a single task to its designated queue.

        Waits for broker confirm before returning.
        Raises on unrecoverable publish failure.
        """
        routing_key = _ROUTING_KEYS.get(task.task_type)
        if routing_key is None:
            raise ValueError(f"No routing key for task_type={task.task_type!r}")

        spec = QUEUE_SPECS.get(routing_key)
        queue_name = spec.name if spec else routing_key

        exchange = await self._get_exchange()
        body = task.to_bytes()

        msg = Message(
            body=body,
            delivery_mode=DeliveryMode.PERSISTENT,
            priority=task.priority,
            content_type="application/json",
            headers={
                "x-task-id":       task.task_id,
                "x-task-type":     task.task_type.value,
                "x-retry-count":   str(task.retry_count),
                "x-case-id":       task.case_id or "",
            },
        )

        t0 = time.perf_counter()
        try:
            await exchange.publish(msg, routing_key=routing_key)
            elapsed = time.perf_counter() - t0
            QUEUE_METRICS.published.labels(queue=queue_name, task_type=task.task_type.value).inc()
            QUEUE_METRICS.publish_latency.labels(queue=queue_name).observe(elapsed)
            self._log.debug(
                "queue.published",
                task_id=task.task_id,
                task_type=task.task_type.value,
                queue=queue_name,
                retry_count=task.retry_count,
                elapsed_ms=round(elapsed * 1000, 1),
            )
        except Exception as exc:
            QUEUE_METRICS.publish_errors.labels(
                queue=queue_name,
                error_type=type(exc).__name__,
            ).inc()
            self._log.error(
                "queue.publish_failed",
                task_id=task.task_id,
                task_type=task.task_type.value,
                error=str(exc),
            )
            # Invalidate channel so next call rebuilds it
            self._channel = None
            self._exchange = None
            raise

    async def publish_many(self, tasks: list[AnyTask]) -> int:
        """Publish a batch of tasks.  Returns the number successfully published."""
        published = 0
        for task in tasks:
            try:
                await self.publish(task)
                published += 1
            except Exception as exc:
                self._log.warning(
                    "queue.batch_publish_partial_failure",
                    task_id=task.task_id,
                    error=str(exc),
                )
        return published

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _get_exchange(self) -> aio_pika.Exchange:
        if self._exchange is not None and self._channel is not None and not self._channel.is_closed:
            return self._exchange

        async with self._lock:
            if self._exchange is not None and self._channel is not None and not self._channel.is_closed:
                return self._exchange

            conn    = await get_connection()
            channel = await conn.channel()
            # Publisher confirms: channel.confirm_select() ensures each publish
            # is ack'd by the broker before returning.
            await channel.set_qos(prefetch_count=0)  # unlimited for publisher
            self._channel  = channel
            self._exchange = await channel.get_exchange(MAIN_EXCHANGE)
        return self._exchange


# ---------------------------------------------------------------------------
# Process-level singleton
# ---------------------------------------------------------------------------

_publisher: TaskPublisher | None = None
_publisher_lock = asyncio.Lock()


async def get_publisher() -> TaskPublisher:
    """Return the shared TaskPublisher, creating it on first call."""
    global _publisher
    if _publisher is not None:
        return _publisher
    async with _publisher_lock:
        if _publisher is None:
            _publisher = TaskPublisher()
    return _publisher
