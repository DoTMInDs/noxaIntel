from django.db import models


class ModelAccuracyReport(models.Model):
    model_name = models.CharField(max_length=100)
    total_predictions = models.IntegerField(default=0)
    correct_predictions = models.IntegerField(default=0)
    accuracy_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    roi_percentage = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        return f"{self.model_name} Accuracy: {self.accuracy_percentage}%"


class CacheMetrics(models.Model):
    endpoint_name = models.CharField(max_length=100)
    cache_hits = models.IntegerField(default=0)
    cache_misses = models.IntegerField(default=0)
    hit_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        return f"Cache {self.endpoint_name}: {self.hit_ratio}% Hit Ratio"
