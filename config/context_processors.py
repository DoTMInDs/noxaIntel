from django.conf import settings

def vapid_public_key(request):
    """Expose VAPID public key to all templates."""
    return {
        "VAPID_PUBLIC_KEY": getattr(settings, "VAPID_PUBLIC_KEY", "")
    }
