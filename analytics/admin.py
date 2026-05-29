from django.contrib import admin
from .models import ModelAccuracyReport, CacheMetrics


@admin.register(ModelAccuracyReport)
class ModelAccuracyReportAdmin(admin.ModelAdmin):
    list_display = ('model_name', 'accuracy_percentage', 'roi_percentage', 'total_predictions', 'correct_predictions', 'recorded_at')
    list_filter = ('model_name', 'recorded_at')
    readonly_fields = ('recorded_at',)


@admin.register(CacheMetrics)
class CacheMetricsAdmin(admin.ModelAdmin):
    list_display = ('endpoint_name', 'hit_ratio', 'cache_hits', 'cache_misses', 'recorded_at')
    list_filter = ('endpoint_name', 'recorded_at')
    readonly_fields = ('recorded_at',)
