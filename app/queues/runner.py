"""
Worker process entrypoint.

Starts all consumers concurrently and runs until SIGTERM / SIGINT.

Usage (Docker):
    python -m app.queues.runner

Usage (dev — runs alongside the API):
    from app.queues.runner import start_workers
    asyncio.create_task(start_workers())

Architecture:
  - Each consumer runs in its own asyncio task, connected to a dedicated channel.
  - A supervision loop monitors each task and restarts it on unexpected exit.
  - Graceful shutdown: SIGTERM cancels all tasks after draining in-flight messages.
  - A periodic depth-poll task refreshes Prometheus queue/DLQ depth gauges.
"""

from __future__ import annotations

import asyncio
import signal
import sys
from typing import Callable, Coroutine, Any

import structlog

from app.core.logging.setup import configure_logging
from app.queues.connection import close_connection, get_connection
from app.queues.consumer import BaseConsumer
from app.queues.metrics import QUEUE_METRICS
from app.queues.topology import QUEUE_SPECS, declare_topology
from app.queues.workers import (
    EmbeddingWorker,
    EvaluationWorker,
    IngestionWorker,
    NotificationWorker,
    OCRWorker,
)

logger = structlog.get_logger(__name__)

_SHUTDOWN_TIMEOUT_SECONDS = 30
_DEPTH_POLL_INTERVAL      = 30   # seconds


# ---------------------------------------------------------------------------
# Worker registry
# ---------------------------------------------------------------------------

def _build_workers() -> list[BaseConsumer]:
    """Instantiate all worker classes.  Concurrency: one instance per worker type."""
    return [
        IngestionWorker(),
        OCRWorker(),
        EmbeddingWorker(),
        EvaluationWorker(),
        NotificationWorker(),
    ]


# ---------------------------------------------------------------------------
# Supervision loop
# ---------------------------------------------------------------------------

async def _supervise(worker: BaseConsumer, stop_event: asyncio.Event) -> None:
    """
    Restart a consumer if it crashes unexpectedly.
    Exits cleanly when stop_event is set.
    """
    worker_type = type(worker).__name__
    QUEUE_METRICS.workers_active.labels(worker_type=worker_type).inc()

    while not stop_event.is_set():
        try:
            await worker.start()
            # Consume until the stop event fires
            while not stop_event.is_set():
                await asyncio.sleep(1.0)
            break
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error(
                "worker.crashed_restarting",
                worker=worker_type,
                error=str(exc),
            )
            # Brief back-off before restart
            await asyncio.sleep(5.0)
        finally:
            try:
                await worker.stop()
            except Exception:
                pass

    QUEUE_METRICS.workers_active.labels(worker_type=worker_type).dec()
    logger.info("worker.stopped", worker=worker_type)


# ---------------------------------------------------------------------------
# Queue depth poller
# ---------------------------------------------------------------------------

async def _poll_queue_depths(stop_event: asyncio.Event) -> None:
    """Periodically fetch approximate queue depths from RabbitMQ management API."""
    from app.core.config.settings import get_settings
    settings = get_settings()

    # Parse management API URL from AMQP URL
    # amqp://user:pass@host:5672/ → http://user:pass@host:15672/api/
    mgmt_url = _amqp_to_mgmt_url(settings.rabbitmq_url)
    if not mgmt_url:
        logger.debug("depth_poll.no_management_url")
        return

    import httpx
    while not stop_event.is_set():
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{mgmt_url}/api/queues/%2F")
                if resp.status_code == 200:
                    for q in resp.json():
                        name     = q.get("name", "")
                        messages = q.get("messages", 0)
                        is_dlq   = name.endswith(".dlq")
                        if is_dlq:
                            QUEUE_METRICS.dlq_depth.labels(queue=name).set(messages)
                        else:
                            QUEUE_METRICS.queue_depth.labels(queue=name).set(messages)
                        consumers = q.get("consumers", 0)
                        QUEUE_METRICS.consumer_count.labels(queue=name).set(consumers)
        except Exception as exc:
            logger.debug("depth_poll.failed", error=str(exc))

        for _ in range(_DEPTH_POLL_INTERVAL):
            if stop_event.is_set():
                break
            await asyncio.sleep(1.0)


def _amqp_to_mgmt_url(amqp_url: str) -> str | None:
    """Convert amqp://user:pass@host:5672/ to http://user:pass@host:15672"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(amqp_url)
        scheme = "https" if parsed.scheme == "amqps" else "http"
        host   = parsed.hostname or "localhost"
        mgmt_port = 15672
        userinfo  = ""
        if parsed.username:
            userinfo = f"{parsed.username}:{parsed.password or ''}@"
        return f"{scheme}://{userinfo}{host}:{mgmt_port}"
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def start_workers(stop_event: asyncio.Event | None = None) -> None:
    """
    Initialize topology, start all workers, and run until stop_event.

    Can be awaited directly (e.g., from tests) or called from __main__.
    """
    if stop_event is None:
        stop_event = asyncio.Event()

    # 1. Connect and declare topology
    conn = await get_connection()
    channel = await conn.channel()
    await declare_topology(channel)
    await channel.close()
    logger.info("worker_runner.topology_ready")

    # 2. Start all supervisor coroutines
    workers = _build_workers()
    tasks: list[asyncio.Task] = [
        asyncio.create_task(_supervise(w, stop_event), name=type(w).__name__)
        for w in workers
    ]

    # 3. Start depth poller
    tasks.append(
        asyncio.create_task(_poll_queue_depths(stop_event), name="depth_poller")
    )

    logger.info("worker_runner.started", worker_count=len(workers))

    # 4. Wait until stop_event is set
    await stop_event.wait()

    # 5. Cancel all tasks
    logger.info("worker_runner.shutting_down")
    for task in tasks:
        task.cancel()

    done, pending = await asyncio.wait(tasks, timeout=_SHUTDOWN_TIMEOUT_SECONDS)

    if pending:
        logger.warning("worker_runner.shutdown_timeout", pending=len(pending))
        for t in pending:
            t.cancel()

    await close_connection()
    logger.info("worker_runner.shutdown_complete")


def _install_signal_handlers(stop_event: asyncio.Event, loop: asyncio.AbstractEventLoop) -> None:
    def _handle(sig: signal.Signals) -> None:
        logger.info("worker_runner.signal_received", signal=sig.name)
        loop.call_soon_threadsafe(stop_event.set)

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle, sig)
        except NotImplementedError:
            # Windows does not support add_signal_handler
            signal.signal(sig, lambda s, f: loop.call_soon_threadsafe(stop_event.set))


if __name__ == "__main__":
    configure_logging()
    logger.info("worker_runner.main_starting")

    loop      = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    stop_evt  = asyncio.Event()
    _install_signal_handlers(stop_evt, loop)

    try:
        loop.run_until_complete(start_workers(stop_evt))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
        logger.info("worker_runner.exited")
        sys.exit(0)
