"""
Reviewer notification hooks for the clarification loop.

Dispatches NotificationPayload events to configured notification backends.

Supported backends (configured via settings):
  - webhook:  HTTP POST to a configurable URL (primary)
  - log:      Structured log entry (always active, useful for dev/test)
  - noop:     Silent, for testing

The notifier is fire-and-forget — notification failures are logged but
never raise exceptions that would break the workflow.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.services.clarification.models import NotificationEvent, NotificationPayload

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Backend protocol
# ---------------------------------------------------------------------------

class NotificationBackend:
    """Base class for notification backends."""

    async def send(self, payload: NotificationPayload) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Log backend (always active)
# ---------------------------------------------------------------------------

class LogNotificationBackend(NotificationBackend):
    """Emits a structured log entry for every notification event."""

    async def send(self, payload: NotificationPayload) -> None:
        logger.info(
            "clarification.notification",
            event=payload.event.value,
            case_id=payload.case_id,
            attempt_id=payload.attempt_id,
            attempt_number=payload.attempt_number,
            question_preview=(payload.question or "")[:80],
            reason=payload.reason,
        )


# ---------------------------------------------------------------------------
# Webhook backend
# ---------------------------------------------------------------------------

class WebhookNotificationBackend(NotificationBackend):
    """
    POST NotificationPayload to a webhook URL as JSON.

    Retries once on transient failure.  Timeout: 5 seconds per attempt.
    """

    def __init__(self, webhook_url: str, secret: str | None = None) -> None:
        self._url = webhook_url
        self._secret = secret

    async def send(self, payload: NotificationPayload) -> None:
        try:
            import httpx
        except ImportError:
            logger.warning("clarification.notifier.httpx_missing")
            return

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._secret:
            headers["X-Webhook-Secret"] = self._secret

        body = {
            "event":          payload.event.value,
            "case_id":        payload.case_id,
            "attempt_id":     payload.attempt_id,
            "attempt_number": payload.attempt_number,
            "question":       payload.question,
            "response":       payload.response,
            "reason":         payload.reason,
            "metadata":       payload.metadata,
            "timestamp":      payload.timestamp.isoformat(),
        }

        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(self._url, json=body, headers=headers)
                    resp.raise_for_status()
                    logger.debug(
                        "clarification.notifier.webhook_sent",
                        event=payload.event.value,
                        case_id=payload.case_id,
                        status_code=resp.status_code,
                    )
                    return
            except Exception as exc:
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
                logger.error(
                    "clarification.notifier.webhook_failed",
                    event=payload.event.value,
                    case_id=payload.case_id,
                    error=str(exc),
                )


# ---------------------------------------------------------------------------
# Noop backend (testing)
# ---------------------------------------------------------------------------

class NoopNotificationBackend(NotificationBackend):
    async def send(self, payload: NotificationPayload) -> None:
        pass


# ---------------------------------------------------------------------------
# Notifier facade
# ---------------------------------------------------------------------------

class ReviewerNotifier:
    """
    Routes notification events to one or more backends.

    Always includes the log backend.  Webhook is added when configured.
    All errors are swallowed — notifications must never break the workflow.
    """

    def __init__(self, backends: list[NotificationBackend]) -> None:
        self._backends = backends

    async def notify(self, payload: NotificationPayload) -> None:
        for backend in self._backends:
            try:
                await backend.send(payload)
            except Exception as exc:
                logger.error(
                    "clarification.notifier.backend_error",
                    backend=type(backend).__name__,
                    event=payload.event.value,
                    case_id=payload.case_id,
                    error=str(exc),
                )
        self._track_notification_metric(payload)

    @staticmethod
    def _track_notification_metric(payload: NotificationPayload) -> None:
        try:
            from app.monitoring.metrics import CLARIFICATION_NOTIFICATIONS_TOTAL
            CLARIFICATION_NOTIFICATIONS_TOTAL.labels(
                event=payload.event.value,
            ).inc()
        except Exception:
            pass

    @classmethod
    def from_settings(cls) -> "ReviewerNotifier":
        """Build notifier from application settings."""
        backends: list[NotificationBackend] = [LogNotificationBackend()]
        try:
            from app.core.config.settings import get_settings
            settings = get_settings()
            webhook_url = getattr(settings, "clarification_webhook_url", None)
            if webhook_url:
                secret = getattr(settings, "clarification_webhook_secret", None)
                backends.append(WebhookNotificationBackend(webhook_url, secret))
        except Exception:
            pass
        return cls(backends=backends)

    @classmethod
    def noop(cls) -> "ReviewerNotifier":
        """No-op notifier for testing."""
        return cls(backends=[NoopNotificationBackend()])
