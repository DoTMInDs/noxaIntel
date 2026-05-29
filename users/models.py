from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class CustomUser(AbstractUser):
    """Custom user model for the AI soccer betting platform."""
    pass


class SubscriptionTier(models.Model):
    name = models.CharField(max_length=50, unique=True)
    price = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    description = models.TextField(blank=True)
    access_advanced_ai = models.BooleanField(default=False)
    access_vip_tips = models.BooleanField(default=False)
    access_ai_assistant = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Profile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    subscription_tier = models.ForeignKey(
        SubscriptionTier, on_delete=models.SET_NULL, null=True, blank=True
    )
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    favorite_leagues = models.CharField(max_length=255, blank=True, help_text="Comma-separated league codes")

    def __str__(self):
        return f"{self.user.username} Profile"


@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        tier, _ = SubscriptionTier.objects.get_or_create(
            name="Free",
            defaults={
                'price': 0.00,
                'description': 'Basic access to match dashboard and standard predictions.',
                'access_advanced_ai': False,
                'access_vip_tips': False,
                'access_ai_assistant': False
            }
        )
        Profile.objects.create(user=instance, subscription_tier=tier)


@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
