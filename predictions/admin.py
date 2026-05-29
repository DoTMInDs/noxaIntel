from django.contrib import admin
from .models import Prediction, AIAnalysis


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ('match', 'recommended_pick', 'confidence_score', 'is_vip_only', 'updated_at')
    list_filter = ('is_vip_only', 'confidence_score')
    search_fields = ('match__home_team__name', 'match__away_team__name')
    readonly_fields = ('updated_at',)


@admin.register(AIAnalysis)
class AIAnalysisAdmin(admin.ModelAdmin):
    list_display = ('match', 'updated_at')
    search_fields = ('match__home_team__name', 'match__away_team__name')
    readonly_fields = ('updated_at',)
