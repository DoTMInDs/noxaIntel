from django.contrib import admin
from .models import Wallet, Transaction, WithdrawalRequest


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'currency', 'is_locked', 'updated_at')
    list_filter = ('currency', 'is_locked')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('updated_at',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'wallet', 'type', 'amount', 'status', 'reference', 'created_at')
    list_filter = ('type', 'status', 'created_at')
    search_fields = ('wallet__user__username', 'wallet__user__email', 'reference', 'description')
    readonly_fields = ('wallet', 'type', 'amount', 'balance_before', 'balance_after', 'status', 'reference', 'description', 'meta', 'created_at')


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'wallet', 'amount', 'bank_name', 'account_number', 'account_name', 'status', 'requested_at')
    list_filter = ('status', 'bank_name', 'requested_at')
    search_fields = ('wallet__user__username', 'wallet__user__email', 'account_name', 'account_number', 'transfer_code')
    readonly_fields = ('requested_at', 'paystack_recipient_code', 'transfer_code')
    actions = ['approve_payout_manually', 'reject_payout_manually']

    def approve_payout_manually(self, request, queryset):
        """Approve and complete payout status manually."""
        for wr in queryset.filter(status='PENDING'):
            wr.status = 'COMPLETED'
            wr.save()
            # Mark the associated transaction as completed
            if wr.transaction:
                wr.transaction.status = 'COMPLETED'
                wr.transaction.save()
    approve_payout_manually.short_description = "Approve and complete payout status manually"

    def reject_payout_manually(self, request, queryset):
        """Reject payout manually and refund the balance."""
        from django.db import transaction as db_tx
        for wr in queryset.filter(status='PENDING'):
            with db_tx.atomic():
                wr.status = 'FAILED'
                wr.failure_reason = 'Rejected manually by administrator.'
                wr.save()
                # Refund user wallet balance
                wallet = wr.wallet
                wallet.credit(
                    amount=wr.amount,
                    tx_type='BET_REFUND',
                    description=f"Refund: Rejected withdrawal request #{wr.id}",
                )
                if wr.transaction:
                    wr.transaction.status = 'FAILED'
                    wr.transaction.save()
    reject_payout_manually.short_description = "Reject payout manually (Refunds user wallet)"

