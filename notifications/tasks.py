# __future__ import absolute_import, unicode_literals

import json
import logging
from datetime import datetime

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import PushSubscription
from .push_service import send_push_notification

logger = logging.getLogger(__name__)

@shared_task(name='notifications.tasks.send_daily_notifications')
def send_daily_notifications():
    """Send a daily reminder push to all subscribed users.

    The task is scheduled by ``CELERY_BEAT_SCHEDULE`` at 06:00 and 12:00
    (local server time). It iterates over every ``PushSubscription`` and
    sends a simple JSON payload. Real‑world implementations would customise
    the message per user, include a deep‑link URL and honour user
    preferences.
    """
    now = timezone.localtime()
    # Simple message – you can replace this with a richer template.
    payload = json.dumps({
        "title": "NoxaIntel Daily Tip",
        "body": f"Your AI‑powered soccer tip for {now:%A %b %d, %H:%M}" ,
        "url": "/"  # landing page when the user clicks the notification
    })

    subscriptions = PushSubscription.objects.select_related('user').all()
    sent = 0
    failed = 0
    for sub in subscriptions:
        try:
            send_push_notification(
                endpoint=sub.endpoint,
                auth=sub.auth,
                p256dh=sub.p256dh,
                payload=payload,
                ttl=86400,  # 1 day
            )
            sent += 1
        except Exception as exc:  # pragma: no cover – production will log
            logger.error(
                "Failed to push to %s (%s): %s",
                sub.user.username,
                sub.endpoint[:40],
                exc,
            )
            failed += 1

    logger.info(
        "Daily push sent – %d succeeded, %d failed (time=%s)",
        sent,
        failed,
        now.isoformat(),
    )
    return {"sent": sent, "failed": failed, "time": now.isoformat()}
