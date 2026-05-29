from django.urls import path
from . import views

app_name = 'ai_engine'

urlpatterns = [
    path('', views.assistant_chat, name='chat'),
    path('partial/query/', views.assistant_query, name='query_partial'),
]
