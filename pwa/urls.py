from django.urls import path
from . import views

app_name = 'pwa'

urlpatterns = [
    path('manifest.json', views.manifest, name='manifest'),
    path('serviceworker.js', views.service_worker, name='serviceworker'),
    path('offline/', views.offline, name='offline'),
]
