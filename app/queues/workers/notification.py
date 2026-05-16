"""
Notification worker — processes NotificationTask messages.

Delivers notifications across configured channels:
  - in_app   — write to in-app notification table (always attempted)
  - email    — send via SMTP / SendGrid (if configured)
  - sms      — send via Twilio (if configured)
  - webhook  — POST to registered webhook URL

Channels are attempted in parallel; a failure in one channel does not
prevent delivery on others.  The task only fails if ALL channels fail.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.queues.consumer import BaseConsumer
from app.queues.models import AnyTask, NotificationChannel, NotificationTask
from app.queues.topology import QUEUE_SPECS

logger = structlog.get_logger(__name__)


class NotificationWorker(BaseConsumer):

    queue_spec = QUEUE_SPECS["notifications"]

    async def process(self, task: AnyTask) -> None:
        assert isinstance(task, NotificationTask), f"Expected NotificationTask, got {type(task)}"
        log = logger.bind(
            task_id=task.task_id,
            recipient_id=task.recipient_id,
            event=task.event.value,
            channels=[c.value for c in task.channels],
            case_id=task.case_id,
        )
        log.info("notification_worker.started")

        # Always persist in-app notification first
        await self._deliver_in_app(task)

        # Attempt configured channels in parallel
        channel_tasks = []
        for channel in task.channels:
            if channel == NotificationChannel.IN_APP:
                continue  # already done above
            elif channel == NotificationChannel.EMAIL:
                channel_tasks.append(self._deliver_email(task))
            elif channel == NotificationChannel.SMS:
                channel_tasks.append(self._deliver_sms(task))
            elif channel == NotificationChannel.WEBHOOK:
                channel_tasks.append(self._deliver_webhook(task))

        results = await asyncio.gather(*channel_tasks, return_exceptions=True)
        failures = [r for r in results if isinstance(r, Exception)]

        if failures and len(failures) == len(channel_tasks) and channel_tasks:
            raise RuntimeError(
                f"All {len(failures)} delivery channel(s) failed: "
                + "; ".join(str(f) for f in failures)
            )

        if failures:
            log.warning(
                "notification_worker.partial_delivery_failure",
                failed_count=len(failures),
                total_channels=len(channel_tasks),
                errors=[str(f) for f in failures],
            )

        log.info(
            "notification_worker.completed",
            channels_attempted=len(task.channels),
            channels_failed=len(failures),
        )

    # ------------------------------------------------------------------

    async def _deliver_in_app(self, task: NotificationTask) -> None:
        """Persist notification row for the frontend to fetch."""
        try:
            from app.db.session.database import get_db_session
            async with get_db_session() as session:
                from sqlalchemy import text
                await session.execute(
                    text(
                        "INSERT INTO notifications "
                        "(notification_id, recipient_id, event_type, subject, body, case_id, task_id, is_read) "
                        "VALUES (:nid, :rid, :event, :subj, :body, :cid, :tid, 0)"
                    ),
                    {
                        "nid":   task.task_id,
                        "rid":   task.recipient_id,
                        "event": task.event.value,
                        "subj":  task.subject or task.event.value.replace("_", " ").title(),
                        "body":  task.body[:4096],
                        "cid":   task.case_id or "",
                        "tid":   task.task_id,
                    },
                )
                await session.commit()
        except Exception as exc:
            logger.warning("notification_worker.in_app_failed", error=str(exc))

    async def _deliver_email(self, task: NotificationTask) -> None:
        """Send email via SMTP.  Skips gracefully if SMTP is not configured."""
        from app.core.config.settings import get_settings
        settings = get_settings()

        smtp_host = getattr(settings, "smtp_host", None)
        if not smtp_host or not task.recipient_email:
            logger.debug(
                "notification_worker.email_skipped",
                reason="no smtp_host or no recipient_email",
            )
            return

        try:
            import aiosmtplib
            from email.mime.text import MIMEText

            msg = MIMEText(task.body, "html" if "<" in task.body else "plain")
            msg["Subject"] = task.subject or task.event.value
            msg["From"]    = getattr(settings, "smtp_from", "noreply@pa-review.com")
            msg["To"]      = task.recipient_email

            await aiosmtplib.send(
                msg,
                hostname=smtp_host,
                port=getattr(settings, "smtp_port", 587),
                username=getattr(settings, "smtp_user", None),
                password=getattr(settings, "smtp_password", None),
                use_tls=getattr(settings, "smtp_use_tls", True),
                timeout=15,
            )
            logger.info("notification_worker.email_sent", to=task.recipient_email)
        except ImportError:
            logger.debug("notification_worker.email_skipped", reason="aiosmtplib not installed")
        except Exception as exc:
            logger.warning(
                "notification_worker.email_failed",
                to=task.recipient_email,
                error=str(exc),
            )
            raise

    async def _deliver_sms(self, task: NotificationTask) -> None:
        """Send SMS via Twilio.  Skips if not configured."""
        from app.core.config.settings import get_settings
        settings = get_settings()

        twilio_sid = getattr(settings, "twilio_account_sid", None)
        if not twilio_sid or not task.recipient_phone:
            logger.debug(
                "notification_worker.sms_skipped",
                reason="no twilio_account_sid or no recipient_phone",
            )
            return

        try:
            from twilio.rest import Client
            client = Client(
                twilio_sid,
                getattr(settings, "twilio_auth_token", ""),
            )
            body_text = task.body[:160] if task.body else task.event.value
            client.messages.create(
                body=body_text,
                from_=getattr(settings, "twilio_from_number", ""),
                to=task.recipient_phone,
            )
            logger.info("notification_worker.sms_sent", to=task.recipient_phone)
        except ImportError:
            logger.debug("notification_worker.sms_skipped", reason="twilio not installed")
        except Exception as exc:
            logger.warning(
                "notification_worker.sms_failed",
                to=task.recipient_phone,
                error=str(exc),
            )
            raise

    async def _deliver_webhook(self, task: NotificationTask) -> None:
        """POST notification payload to a registered webhook URL."""
        webhook_url = task.metadata.get("webhook_url")
        if not webhook_url:
            logger.debug("notification_worker.webhook_skipped", reason="no webhook_url in metadata")
            return

        import httpx
        payload = {
            "event":        task.event.value,
            "recipient_id": task.recipient_id,
            "case_id":      task.case_id,
            "subject":      task.subject,
            "body":         task.body,
            "task_id":      task.task_id,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
        logger.info("notification_worker.webhook_sent", url=webhook_url, status=resp.status_code)
