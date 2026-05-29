from django.db import models
from users.models import CustomUser


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('MATCH_START', 'Match Start'),
        ('GOAL', 'Goal Scored'),
        ('TIP_ALERT', 'High Confidence Tip'),
        ('PREDICTION', 'New Prediction'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='TIP_ALERT')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    url = models.CharField(max_length=500, blank=True, default='/')  # Deep-link URL

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self):
        return f"Alert for {self.user.username}: {self.message}"


class PushSubscription(models.Model):
    """Stores a browser Web Push subscription for a user device."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.TextField(unique=True)
    p256dh = models.TextField()   # Browser public key
    auth = models.TextField()     # Auth secret
    created_at = models.DateTimeField(auto_now_add=True)
    user_agent = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Push sub for {self.user.username} ({self.endpoint[:40]}...)"
