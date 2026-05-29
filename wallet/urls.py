from django.urls import path
from . import views

app_name = 'wallet'

urlpatterns = [
    path('wallet/', views.overview, name='overview'),
    path('wallet/deposit/', views.deposit_initiate, name='deposit'),
    path('wallet/deposit/verify/', views.deposit_verify, name='deposit_verify'),
    path('wallet/withdraw/', views.withdraw_request, name='withdraw'),
    path('wallet/paystack/webhook/', views.paystack_webhook, name='webhook'),
    path('wallet/balance/partial/', views.balance_partial, name='balance_partial'),
    path('wallet/banks/', views.list_banks, name='banks'),
    path('wallet/verify-account/', views.verify_account, name='verify_account'),
    
    # Real-Time payment/withdrawal simulations
    path('wallet/deposit/simulate/<str:reference>/', views.deposit_simulate, name='deposit_simulate'),
    path('wallet/deposit/simulate/<str:reference>/approve/', views.deposit_simulate_approve, name='deposit_simulate_approve'),
    path('wallet/withdraw/simulate/<int:pk>/', views.withdraw_simulate, name='withdraw_simulate'),
    path('wallet/withdraw/simulate/<int:pk>/process/', views.withdraw_simulate_process, name='withdraw_simulate_process'),
    path('wallet/withdraw/simulate/<int:pk>/settle/', views.withdraw_simulate_settle, name='withdraw_simulate_settle'),
    path('wallet/withdraw/status/<int:pk>/', views.withdraw_status, name='withdraw_status'),
]
