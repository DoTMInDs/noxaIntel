from django.urls import path
from . import views

app_name = 'betting'

urlpatterns = [
    # AI Tips Dashboard
    path('', views.tips_dashboard, name='dashboard'),
    path('partial/filter/', views.tips_filter_partial, name='filter_partial'),
    
    # Sportsbook Selections & Wallet Bets
    path('betslip/', views.betslip_page, name='betslip'),
    path('bet/place/', views.place_bet, name='place_bet'),
    path('bet/my-bets/', views.my_bets, name='my_bets'),
    path('bet/<int:pk>/', views.bet_detail, name='bet_detail'),
    path('bet/<int:pk>/cashout/', views.cash_out, name='cash_out'),
]
