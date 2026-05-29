from django.db import models
from matches.models import Match


class Prediction(models.Model):
    match = models.OneToOneField(Match, on_delete=models.CASCADE, related_name='prediction')
    home_win_prob = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage 0-100")
    draw_prob = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage 0-100")
    away_win_prob = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage 0-100")
    over_2_5_prob = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage 0-100")
    under_2_5_prob = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage 0-100")
    btts_yes_prob = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage 0-100")
    btts_no_prob = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage 0-100")
    confidence_score = models.IntegerField(help_text="0-100 scale")
    recommended_pick = models.CharField(max_length=100)
    is_vip_only = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-confidence_score']

    def __str__(self):
        return f"Prediction for {self.match} (Conf: {self.confidence_score}%)"


class AIAnalysis(models.Model):
    match = models.OneToOneField(Match, on_delete=models.CASCADE, related_name='ai_analysis')
    tactical_breakdown = models.TextField()
    key_player_matchups = models.TextField()
    weather_impact = models.CharField(max_length=255, blank=True)
    final_verdict = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"AI Analysis for {self.match}"
