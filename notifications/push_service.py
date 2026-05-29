"""
Push notification service for NoxaIntel.
Sends Web Push messages to all of a user's subscribed devices using pywebpush.
"""
import json
import logging
import base64

from django.conf import settings
from pywebpush import webpush, WebPushException

logger = logging.getLogger(__name__)


def _get_vapid_private_key_pem() -> str:
    """Decode the base64-encoded PEM private key from settings."""
    raw = settings.VAPID_PRIVATE_KEY
    try:
        decoded = base64.urlsafe_b64decode(raw + '==')
        return decoded.decode('utf-8')
    except Exception:
        return raw  # Already PEM string


def send_push_notification(user, title: str, body: str, url: str = '/', icon: str = '/static/icons/icon-192.png'):
    """
    Send a Web Push notification to all of a user's active subscriptions.

    Args:
        user: CustomUser instance
        title: Notification title
        body:  Notification body text
        url:   URL to open when the user clicks the notification
        icon:  Icon URL for the notification
    """
    from notifications.models import PushSubscription

    subscriptions = PushSubscription.objects.filter(user=user)
    if not subscriptions.exists():
        return

    vapid_claims = {"sub": f"mailto:{settings.VAPID_ADMIN_EMAIL}"}
    private_key_pem = _get_vapid_private_key_pem()
    vapid_public_key = settings.VAPID_PUBLIC_KEY

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url,
        "icon": icon,
        "badge": "/static/icons/badge-72.png",
        "tag": "noxaintel-alert",
        "renotify": True,
    })

    stale_ids = []
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth,
                    },
                },
                data=payload,
                vapid_private_key=private_key_pem,
                vapid_claims=vapid_claims,
            )
            logger.info(f"Push sent to {user.username} → {sub.endpoint[:50]}")
        except WebPushException as e:
            status = e.response.status_code if e.response is not None else None
            if status in (404, 410):
                # Subscription expired or unsubscribed — clean up
                stale_ids.append(sub.id)
                logger.warning(f"Stale push subscription removed for {user.username} (status {status})")
            else:
                logger.error(f"Push failed for {user.username}: {e}")
        except Exception as e:
            logger.error(f"Unexpected push error for {user.username}: {e}")

    if stale_ids:
        PushSubscription.objects.filter(id__in=stale_ids).delete()


def notify_user(user, title: str, body: str, notification_type: str = 'TIP_ALERT', url: str = '/'):
    """
    Create an in-app Notification record AND send a Web Push for a user.
    Use this as the single entry point whenever you want to alert a user.
    """
    from notifications.models import Notification
    notif = Notification.objects.create(
        user=user,
        message=body,
        notification_type=notification_type,
        url=url,
    )
    send_push_notification(user, title=title, body=body, url=url)
    return notif
