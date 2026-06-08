from decimal import Decimal
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

    # AI Exact Score Prediction
    predicted_home_score = models.IntegerField(null=True, blank=True, help_text="AI predicted home goals")
    predicted_away_score = models.IntegerField(null=True, blank=True, help_text="AI predicted away goals")

    class Meta:
        ordering = ['-confidence_score']

    def __str__(self):
        return f"Prediction for {self.match} (Conf: {self.confidence_score}%)"

    @property
    def predicted_exact_score(self):
        """Returns formatted predicted scoreline, e.g. '2 - 1'."""
        if self.predicted_home_score is not None and self.predicted_away_score is not None:
            return f"{self.predicted_home_score} - {self.predicted_away_score}"
        return None

    def get_correct_score_odds(self):
        """
        Derives correct score odds from the latest 1X2 moneyline odds.
        Correct scores are rare events so we apply a rarity multiplier.
        Draws (e.g. 0-0, 1-1) use draw_odds * 2.5; home wins use home_odds * 3.8;
        away wins use away_odds * 4.2.
        """
        try:
            odds_snapshot = self.match.odds_snapshots.first()
            if not odds_snapshot:
                return Decimal('8.00')

            hs = self.predicted_home_score or 0
            aws = self.predicted_away_score or 0

            if hs == aws:
                base = odds_snapshot.draw_odds or Decimal('3.50')
                multiplier = Decimal('2.50')
            elif hs > aws:
                base = odds_snapshot.home_odds or Decimal('2.00')
                multiplier = Decimal('3.80')
            else:
                base = odds_snapshot.away_odds or Decimal('2.50')
                multiplier = Decimal('4.20')

            raw_odds = base * multiplier
            # Cap between 3.50 and 50.00 for realism
            return round(min(max(raw_odds, Decimal('3.50')), Decimal('50.00')), 2)
        except Exception:
            return Decimal('8.00')


class AIAnalysis(models.Model):
    match = models.OneToOneField(Match, on_delete=models.CASCADE, related_name='ai_analysis')
    tactical_breakdown = models.TextField()
    key_player_matchups = models.TextField()
    weather_impact = models.CharField(max_length=255, blank=True)
    final_verdict = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"AI Analysis for {self.match}"
