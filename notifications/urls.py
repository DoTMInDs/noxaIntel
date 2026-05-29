from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('partial/badge/', views.notification_badge_partial, name='badge_partial'),
    path('<int:notification_id>/read/', views.mark_as_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    # Web Push subscription endpoints
    path('push/subscribe/', views.save_push_subscription, name='push_subscribe'),
    path('push/unsubscribe/', views.delete_push_subscription, name='push_unsubscribe'),
    path('push/test/', views.send_test_push, name='push_test'),
]
