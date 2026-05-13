"""
Structured logging configuration using Structlog.

Design:
- JSON renderer in production/staging for log aggregation (Datadog, ELK, CloudWatch)
- Rich console renderer in development for human readability
- Async-safe context variables for request_id, trace_id, user_id
- Integration with Python stdlib logging so third-party libraries (SQLAlchemy,
  uvicorn, etc.) also emit structured JSON

Usage:
    configure_logging()   # call once at startup

    logger = structlog.get_logger(__name__)
    logger.info("event.name", key="value", count=42)
"""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.types import EventDict, WrappedLogger

from app.core.config.settings import get_settings


def _add_severity_field(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Map structlog level names to GCP / Datadog severity field.
    Some log aggregators expect 'severity' rather than 'level'.
    """
    level_map = {
        "debug": "DEBUG",
        "info": "INFO",
        "warning": "WARNING",
        "error": "ERROR",
        "critical": "CRITICAL",
    }
    event_dict["severity"] = level_map.get(method_name, "INFO")
    return event_dict


def _drop_color_message_key(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Uvicorn adds a 'color_message' key that duplicates 'message' with ANSI codes.
    Drop it to keep JSON output clean.
    """
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging() -> None:
    """
    Configure structlog and stdlib logging.

    Call exactly once during application startup (in lifespan handler).
    """
    settings = get_settings()
    log_level = getattr(logging, settings.log_level, logging.INFO)

    # ----------------------------------------------------------
    # Shared processors applied to every log record
    # ----------------------------------------------------------
    shared_processors: list[structlog.types.Processor] = [
        # Merge context variables bound via structlog.contextvars.bind_contextvars()
        structlog.contextvars.merge_contextvars,
        # Add log level to event dict
        structlog.stdlib.add_log_level,
        # Add logger name
        structlog.stdlib.add_logger_name,
        # Add GCP/Datadog severity field
        _add_severity_field,
        # Drop uvicorn noise
        _drop_color_message_key,
        # Add ISO 8601 timestamp
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Render exception info if present
        structlog.processors.format_exc_info,
        # Include stack info if requested
        structlog.processors.StackInfoRenderer(),
    ]

    # ----------------------------------------------------------
    # Renderer: JSON for production/staging, console for dev
    # ----------------------------------------------------------
    if settings.log_format == "console":
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    # ----------------------------------------------------------
    # Configure structlog
    # ----------------------------------------------------------
    structlog.configure(
        processors=shared_processors
        + [
            # Prepare event dict for stdlib logging bridge
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # ----------------------------------------------------------
    # Configure stdlib logging (bridges third-party loggers)
    # ----------------------------------------------------------
    formatter = structlog.stdlib.ProcessorFormatter(
        # Final processors run on records coming from stdlib
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Suppress noisy third-party loggers
    for noisy_logger in [
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "aio_pika",
        "aiormq",
        "httpx",
        "httpcore",
    ]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # Suppress access logs — we handle them in RequestLoggingMiddleware
    logging.getLogger("uvicorn.access").propagate = False
