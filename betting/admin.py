from django.contrib import admin
from .models import BettingTip


@admin.register(BettingTip)
class BettingTipAdmin(admin.ModelAdmin):
    list_display = ('match', 'tip_type', 'odds', 'confidence_score', 'is_vip_only', 'created_at')
    list_filter = ('tip_type', 'is_vip_only', 'created_at')
    search_fields = ('match__home_team__name', 'match__away_team__name', 'description')
    readonly_fields = ('created_at',)
