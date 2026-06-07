from django.contrib import admin
from .models import Notification, PushSubscription


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('user__username', 'message')
    readonly_fields = ('created_at',)


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'endpoint', 'created_at', 'user_agent')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'endpoint', 'user_agent')
    readonly_fields = ('created_at',)
