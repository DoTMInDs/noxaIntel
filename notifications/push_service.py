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


def send_fcm_notification(user, title: str, body: str, url: str = '/', icon: str = '/static/imgs/icons/icon-192x192.png'):
    """
    Sends notification to user's registered FCM devices.
    Logs to console if FCM credentials are not configured.
    """
    from notifications.models import FcmDevice
    import requests

    fcm_credentials = getattr(settings, 'FCM_CREDENTIALS_JSON', '')
    project_id = getattr(settings, 'FCM_PROJECT_ID', '')
    devices = FcmDevice.objects.filter(user=user)

    if not fcm_credentials or not project_id:
        logger.info(f"[FCM Console Log] User: {user.username} | Title: '{title}' | Body: '{body}' | URL: '{url}'")
        return False

    if not devices.exists():
        logger.debug(f"No FCM devices registered for user {user.username}")
        return False

    try:
        import google.oauth2.service_account
        import google.auth.transport.requests

        info = json.loads(fcm_credentials)
        credentials = google.oauth2.service_account.Credentials.from_service_account_info(info)
        scoped_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/firebase.messaging'])

        request = google.auth.transport.requests.Request()
        scoped_credentials.refresh(request)
        access_token = scoped_credentials.token

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        fcm_url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        stale_tokens = []

        for dev in devices:
            payload = {
                "message": {
                    "token": dev.registration_token,
                    "notification": {
                        "title": title,
                        "body": body
                    },
                    "data": {
                        "url": url,
                        "icon": icon
                    }
                }
            }

            response = requests.post(fcm_url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                logger.info(f"FCM push sent successfully to {user.username}'s device.")
            elif response.status_code in (404, 410):
                stale_tokens.append(dev.registration_token)
                logger.warning(f"FCM token stale for user {user.username}: {response.text}")
            else:
                logger.error(f"FCM request failed for {user.username}: Status {response.status_code}, Body {response.text}")

        if stale_tokens:
            FcmDevice.objects.filter(registration_token__in=stale_tokens).delete()

        return True
    except Exception as e:
        logger.error(f"Failed to send FCM notification: {e}")
        logger.info(f"[FCM Console Log (Error Fallback)] User: {user.username} | Title: '{title}' | Body: '{body}' | URL: '{url}'")
        return False


def send_push_notification(user, title: str, body: str, url: str = '/', icon: str = '/static/imgs/icons/icon-192x192.png'):
    """
    Send a Web Push notification to all of a user's active subscriptions and FCM devices.

    Args:
        user: CustomUser instance
        title: Notification title
        body:  Notification body text
        url:   URL to open when the user clicks the notification
        icon:  Icon URL for the notification
    """
    # 1. Send via FCM
    send_fcm_notification(user, title, body, url, icon)

    # 2. Also send via Web Push (pywebpush)
    from notifications.models import PushSubscription

    subscriptions = PushSubscription.objects.filter(user=user)
    if not subscriptions.exists():
        logger.debug(f"No web push subscriptions for user {user.username} — skipping web push")
        return

    vapid_claims = {"sub": f"mailto:{settings.VAPID_ADMIN_EMAIL}"}
    private_key_pem = _get_vapid_private_key_pem()

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url,
        "icon": icon,
        "badge": "/static/imgs/icons/icon-72x72.png",
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
    Create an in-app Notification record AND send a Web Push / FCM for a user.
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
