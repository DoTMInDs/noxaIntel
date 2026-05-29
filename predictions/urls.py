from django.urls import path
from . import views

app_name = 'predictions'

urlpatterns = [
    path('<int:match_id>/', views.prediction_detail, name='detail'),
    path('partial/<int:match_id>/', views.prediction_partial, name='partial'),
]
