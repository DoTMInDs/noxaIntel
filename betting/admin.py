from django.contrib import admin
from .models import BettingTip, BetSlip, BetSelection


@admin.register(BettingTip)
class BettingTipAdmin(admin.ModelAdmin):
    list_display = ('match', 'tip_type', 'odds', 'confidence_score', 'is_vip_only', 'created_at')
    list_filter = ('tip_type', 'is_vip_only', 'created_at')
    search_fields = ('match__home_team__name', 'match__away_team__name', 'description')
    readonly_fields = ('created_at',)


class BetSelectionInline(admin.TabularInline):
    model = BetSelection
    extra = 0
    readonly_fields = ('match', 'market', 'odds_at_placement')


@admin.register(BetSlip)
class BetSlipAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'slip_type', 'total_stake', 'total_odds', 'potential_payout', 'status', 'created_at')
    list_filter = ('status', 'slip_type', 'created_at')
    search_fields = ('user__username', 'user__email', 'id')
    readonly_fields = ('created_at', 'settled_at', 'transaction')
    inlines = [BetSelectionInline]
    actions = ['void_selected_slips', 'settle_as_won_manually']

    def void_selected_slips(self, request, queryset):
        """Action to void selections and slips manually."""
        for slip in queryset.filter(status='SUBMITTED'):
            slip.status = 'VOID'
            slip.save()
    void_selected_slips.short_description = "Void selected bet slips"

    def settle_as_won_manually(self, request, queryset):
        """Manually settle winning bets and credit users."""
        from django.db import transaction as db_tx
        for slip in queryset.filter(status='SUBMITTED'):
            with db_tx.atomic():
                slip.status = 'WON'
                slip.actual_payout = slip.potential_payout
                slip.save()
                # Credit user wallet
                wallet = slip.user.wallet
                wallet.credit(
                    amount=slip.potential_payout,
                    tx_type='BET_WIN',
                    description=f"Manual Win settlement for Bet #{slip.id}",
                )
    settle_as_won_manually.short_description = "Settle selected bet slips as WON (Credits user)"
