from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, SubscriptionTier, Profile


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')


@admin.register(SubscriptionTier)
class SubscriptionTierAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'access_advanced_ai', 'access_vip_tips', 'access_ai_assistant')
    list_filter = ('access_advanced_ai', 'access_vip_tips', 'access_ai_assistant')


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'subscription_tier', 'email_notifications', 'push_notifications')
    list_filter = ('subscription_tier', 'email_notifications', 'push_notifications')
    search_fields = ('user__username', 'user__email')
