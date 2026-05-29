from django.urls import path
from . import views

app_name = 'matches'

urlpatterns = [
    path('', views.match_dashboard, name='dashboard'),
    path('partial/list/', views.match_list_partial, name='list_partial'),
    path('<int:match_id>/', views.match_detail, name='detail'),
]
