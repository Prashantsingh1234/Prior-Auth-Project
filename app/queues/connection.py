"""
RabbitMQ async connection manager.

Provides a singleton robust connection that:
  - Connects lazily on first use
  - Reconnects automatically after broker restarts
  - Exposes a channel pool so workers don't share a single channel
  - Surfaces connection state for health checks

Usage:
    from app.queues.connection import get_connection

    conn = await get_connection()
    channel = await conn.channel()
"""

from __future__ import annotations

import asyncio
from typing import Any

import aio_pika
import structlog
from aio_pika import Connection, RobustConnection
from aio_pika.exceptions import AMQPConnectionError

from app.core.config.settings import get_settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_connection: RobustConnection | None = None
_lock = asyncio.Lock()

_MAX_RECONNECT_ATTEMPTS = 10
_RECONNECT_BASE_DELAY   = 1.0   # seconds
_RECONNECT_MAX_DELAY    = 60.0  # seconds


async def get_connection() -> RobustConnection:
    """
    Return the shared RobustConnection, creating it on first call.

    RobustConnection (aio-pika) automatically re-establishes the TCP connection
    and re-declares channels after a broker restart — no manual reconnect loop needed.
    """
    global _connection
    if _connection is not None and not _connection.is_closed:
        return _connection

    async with _lock:
        # Double-check after acquiring lock
        if _connection is not None and not _connection.is_closed:
            return _connection
        _connection = await _connect_with_retry()
    return _connection


async def close_connection() -> None:
    """Gracefully close the broker connection during application shutdown."""
    global _connection
    if _connection is not None and not _connection.is_closed:
        try:
            await _connection.close()
            logger.info("rabbitmq.connection.closed")
        except Exception as exc:
            logger.warning("rabbitmq.connection.close_failed", error=str(exc))
    _connection = None


async def is_connected() -> bool:
    """Return True if the broker connection is open and usable (for health checks)."""
    try:
        if _connection is None or _connection.is_closed:
            return False
        # Lightweight check: open a transient channel and close it
        ch = await asyncio.wait_for(_connection.channel(), timeout=5.0)
        await ch.close()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _connect_with_retry() -> RobustConnection:
    settings = get_settings()
    attempt   = 0
    delay     = _RECONNECT_BASE_DELAY

    while attempt < _MAX_RECONNECT_ATTEMPTS:
        try:
            conn = await aio_pika.connect_robust(
                settings.rabbitmq_url,
                # RobustConnection parameters
                reconnect_interval=5,
                fail_fast=False,
                # TCP keepalive
                heartbeat=60,
                connection_timeout=30,
                client_properties={"connection_name": "pa-platform"},
            )
            conn.add_close_callback(_on_connection_close)
            logger.info(
                "rabbitmq.connection.established",
                url=_sanitize_url(settings.rabbitmq_url),
                attempt=attempt + 1,
            )
            return conn
        except (AMQPConnectionError, OSError, asyncio.TimeoutError) as exc:
            attempt += 1
            if attempt >= _MAX_RECONNECT_ATTEMPTS:
                logger.error(
                    "rabbitmq.connection.failed",
                    attempts=attempt,
                    error=str(exc),
                )
                raise RuntimeError(
                    f"Cannot connect to RabbitMQ after {attempt} attempts: {exc}"
                ) from exc

            logger.warning(
                "rabbitmq.connection.retry",
                attempt=attempt,
                delay_s=delay,
                error=str(exc),
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, _RECONNECT_MAX_DELAY)


def _on_connection_close(sender: Any, exc: BaseException | None = None) -> None:
    if exc is not None:
        logger.warning("rabbitmq.connection.lost", error=str(exc))
    else:
        logger.info("rabbitmq.connection.closed_gracefully")


def _sanitize_url(url: str) -> str:
    """Replace password in AMQP URL with *** for safe logging."""
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        if parsed.password:
            netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
            return urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        pass
    return "<amqp-url>"
