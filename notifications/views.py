import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Notification, PushSubscription
from .push_service import send_push_notification


@login_required
def notification_list(request):
    """Renders the user's notifications page."""
    notifications = Notification.objects.filter(user=request.user)[:30]
    has_push_sub = PushSubscription.objects.filter(user=request.user).exists()
    return render(request, 'notifications/list.html', {
        'notifications': notifications,
        'has_push_sub': has_push_sub,
    })


@login_required
def notification_badge_partial(request):
    """HTMX polling endpoint returning unread notification count badge."""
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    return render(request, 'notifications/partials/badge.html', {'unread_count': unread_count})


@login_required
def mark_as_read(request, notification_id):
    """HTMX endpoint to mark a notification as read."""
    try:
        notif = Notification.objects.get(id=notification_id, user=request.user)
        notif.is_read = True
        notif.save()
    except Notification.DoesNotExist:
        pass

    if request.htmx:
        notifications = Notification.objects.filter(user=request.user)[:30]
        return render(request, 'notifications/partials/list_items.html', {'notifications': notifications})
    return redirect('notifications:list')


@login_required
def mark_all_read(request):
    """Mark all notifications as read."""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    if request.htmx:
        return render(request, 'notifications/partials/badge.html', {'unread_count': 0})
    return redirect('notifications:list')


@login_required
@require_POST
def save_push_subscription(request):
    """
    Save a browser Web Push subscription to the database.
    Called by the frontend after the user grants notification permission.
    """
    try:
        data = json.loads(request.body)
        endpoint = data.get('endpoint')
        p256dh = data.get('keys', {}).get('p256dh')
        auth = data.get('keys', {}).get('auth')

        if not all([endpoint, p256dh, auth]):
            return JsonResponse({'status': 'error', 'message': 'Invalid subscription data'}, status=400)

        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                'user': request.user,
                'p256dh': p256dh,
                'auth': auth,
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:300],
            }
        )
        return JsonResponse({'status': 'ok', 'message': 'Subscription saved'})
    except (json.JSONDecodeError, KeyError) as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@require_POST
def delete_push_subscription(request):
    """
    Delete a browser Web Push subscription (user opted out).
    """
    try:
        data = json.loads(request.body)
        endpoint = data.get('endpoint')
        if endpoint:
            PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return JsonResponse({'status': 'ok', 'message': 'Subscription removed'})
    except json.JSONDecodeError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@require_http_methods(['GET', 'POST'])
def send_test_push(request):
    """Send a test push notification to the current user (dev convenience endpoint)."""
    send_push_notification(
        user=request.user,
        title='NoxaIntel Test Alert',
        body='Push notifications are working! You will receive real-time match and tip alerts.',
        url='/notifications/',
    )
    return JsonResponse({'status': 'ok', 'message': 'Test push sent'})
