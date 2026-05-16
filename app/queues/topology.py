"""
RabbitMQ topology — exchange, queue, and DLQ declarations.

Topology overview
-----------------

  pa.direct  (direct exchange)
      │
      ├── pa.ingestion    ──DLX──► pa.dlx ──► pa.ingestion.dlq
      ├── pa.ocr          ──DLX──► pa.dlx ──► pa.ocr.dlq
      ├── pa.embedding    ──DLX──► pa.dlx ──► pa.embedding.dlq
      ├── pa.evaluation   ──DLX──► pa.dlx ──► pa.evaluation.dlq
      └── pa.notifications──DLX──► pa.dlx ──► pa.notifications.dlq

  pa.retry  (direct exchange — delayed re-delivery)
      │
      └── pa.retry.{delay_ms}  (TTL queue → DLX → pa.direct → original queue)

Retry flow
----------
  Worker fails → nack(requeue=False)
    → if retry_count < max_retries:
          publish to pa.retry with TTL = 2^retry_count * retry_base_ms
          TTL expires → pa.direct → original routing key → original queue
    → else:
          publish to pa.dlx directly → DLQ

All declarations are idempotent — safe to call on every startup.

Usage:
    from app.queues.topology import declare_topology, QUEUES
    channel = await conn.channel()
    await declare_topology(channel)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import aio_pika
import structlog
from aio_pika import Channel, ExchangeType

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Exchange names (single source of truth)
# ---------------------------------------------------------------------------

MAIN_EXCHANGE  = "pa.direct"
DLX            = "pa.dlx"
RETRY_EXCHANGE = "pa.retry"


# ---------------------------------------------------------------------------
# Queue descriptors
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class QueueSpec:
    name:        str
    routing_key: str
    dlq_name:    str
    # Message TTL in milliseconds (0 = no TTL)
    message_ttl_ms: int = 0
    # Max length before overflow goes to DLQ
    max_length: int | None = None
    # Priority range (0 = no priority)
    max_priority: int = 10


QUEUE_SPECS: dict[str, QueueSpec] = {
    "ingestion": QueueSpec(
        name="pa.ingestion",
        routing_key="ingestion",
        dlq_name="pa.ingestion.dlq",
        message_ttl_ms=3_600_000,  # 1 hour
        max_length=10_000,
    ),
    "ocr": QueueSpec(
        name="pa.ocr",
        routing_key="ocr",
        dlq_name="pa.ocr.dlq",
        message_ttl_ms=3_600_000,
        max_length=5_000,
    ),
    "embedding": QueueSpec(
        name="pa.embedding",
        routing_key="embedding",
        dlq_name="pa.embedding.dlq",
        message_ttl_ms=7_200_000,  # 2 hours
        max_length=50_000,
    ),
    "evaluation": QueueSpec(
        name="pa.evaluation",
        routing_key="evaluation",
        dlq_name="pa.evaluation.dlq",
        message_ttl_ms=1_800_000,  # 30 min
        max_length=2_000,
    ),
    "notifications": QueueSpec(
        name="pa.notifications",
        routing_key="notification",
        dlq_name="pa.notifications.dlq",
        message_ttl_ms=86_400_000,  # 24 hours
        max_length=100_000,
    ),
}

# Convenience mapping: routing_key → QueueSpec
QUEUES: dict[str, QueueSpec] = {v.routing_key: v for v in QUEUE_SPECS.values()}

# Retry delays (ms) — exponential backoff: 5s, 15s, 45s
RETRY_DELAYS_MS = [5_000, 15_000, 45_000]


# ---------------------------------------------------------------------------
# Topology declaration
# ---------------------------------------------------------------------------

async def declare_topology(channel: Channel) -> None:
    """
    Idempotently declare all exchanges, queues, and bindings.

    Called once during startup (or worker startup) before any messages flow.
    """
    # 1. Dead letter exchange — collects all permanently failed messages
    dlx = await channel.declare_exchange(
        DLX,
        ExchangeType.DIRECT,
        durable=True,
    )

    # 2. Retry exchange — direct exchange that routes back to the main exchange
    retry_exchange = await channel.declare_exchange(
        RETRY_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )

    # 3. Main exchange
    main_exchange = await channel.declare_exchange(
        MAIN_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )

    # 4. Work queues + DLQs
    for spec in QUEUE_SPECS.values():
        await _declare_work_queue(channel, spec, main_exchange, dlx)
        await _declare_dlq(channel, spec, dlx)

    # 5. Retry queues (one per delay tier, shared across all task types)
    for delay_ms in RETRY_DELAYS_MS:
        await _declare_retry_queue(channel, delay_ms, retry_exchange, main_exchange)

    logger.info(
        "rabbitmq.topology.declared",
        queues=list(QUEUE_SPECS.keys()),
        retry_delays_ms=RETRY_DELAYS_MS,
    )


async def _declare_work_queue(
    channel: Channel,
    spec: QueueSpec,
    main_exchange: aio_pika.Exchange,
    dlx: aio_pika.Exchange,
) -> aio_pika.Queue:
    args: dict = {
        "x-dead-letter-exchange":     DLX,
        "x-dead-letter-routing-key":  spec.dlq_name,
        "x-max-priority":             spec.max_priority,
    }
    if spec.message_ttl_ms:
        args["x-message-ttl"] = spec.message_ttl_ms
    if spec.max_length is not None:
        args["x-max-length"] = spec.max_length
        args["x-overflow"] = "reject-publish-dlx"

    queue = await channel.declare_queue(
        spec.name,
        durable=True,
        arguments=args,
    )
    await queue.bind(main_exchange, routing_key=spec.routing_key)
    return queue


async def _declare_dlq(
    channel: Channel,
    spec: QueueSpec,
    dlx: aio_pika.Exchange,
) -> aio_pika.Queue:
    dlq = await channel.declare_queue(
        spec.dlq_name,
        durable=True,
        arguments={"x-queue-type": "classic"},
    )
    await dlq.bind(dlx, routing_key=spec.dlq_name)
    return dlq


async def _declare_retry_queue(
    channel: Channel,
    delay_ms: int,
    retry_exchange: aio_pika.Exchange,
    main_exchange: aio_pika.Exchange,
) -> aio_pika.Queue:
    """
    Temporary-TTL queue that holds messages for `delay_ms` then re-routes
    them to the main exchange (using the original routing key stored in
    x-pa-original-routing-key header — set by the consumer on retry publish).
    """
    queue_name = f"pa.retry.{delay_ms}ms"
    queue = await channel.declare_queue(
        queue_name,
        durable=True,
        arguments={
            "x-message-ttl":           delay_ms,
            "x-dead-letter-exchange":  MAIN_EXCHANGE,
            # No x-dead-letter-routing-key — the publisher sets it per-message
            "x-queue-type":            "classic",
        },
    )
    await queue.bind(retry_exchange, routing_key=str(delay_ms))
    return queue
