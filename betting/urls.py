from django.urls import path
from . import views

app_name = 'betting'

urlpatterns = [
    path('', views.tips_dashboard, name='dashboard'),
    path('partial/filter/', views.tips_filter_partial, name='filter_partial'),
]
