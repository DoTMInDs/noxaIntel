# notifications/context_processors.py
"""Context processors for notifications app.
Provides VAPID public key to templates.
"""

from django.conf import settings

def vapid_key(request):
    return {
        "VAPID_PUBLIC_KEY": getattr(settings, "VAPID_PUBLIC_KEY", "")
    }
