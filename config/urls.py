from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/matches/', permanent=False), name='home'),
    path('users/', include('users.urls', namespace='users')),
    path('matches/', include('matches.urls', namespace='matches')),
    path('predictions/', include('predictions.urls', namespace='predictions')),
    path('betting/', include('betting.urls', namespace='betting')),
    path('assistant/', include('ai_engine.urls', namespace='ai_engine')),
    path('notifications/', include('notifications.urls', namespace='notifications')),
    path('analytics/', include('analytics.urls', namespace='analytics')),
    path('pwa/', include('pwa.urls', namespace='pwa')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
