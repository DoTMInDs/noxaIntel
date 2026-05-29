from django.db import models
from django.utils import timezone


class League(models.Model):
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    logo_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.country})"


class Team(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    logo_url = models.URLField(blank=True, null=True)
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='teams')

    def __str__(self):
        return self.name


class Match(models.Model):
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('LIVE', 'Live'),
        ('FINISHED', 'Finished'),
        ('POSTPONED', 'Postponed'),
    ]

    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='matches')
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_matches')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_matches')
    match_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)
    minute = models.CharField(max_length=10, null=True, blank=True, help_text="e.g. 45', HT, FT")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['match_date', 'league', 'status']),
        ]
        ordering = ['match_date']

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} ({self.match_date.strftime('%Y-%m-%d %H:%M')})"

    @property
    def is_live(self):
        return self.status == 'LIVE'


class OddsSnapshot(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='odds_snapshots')
    timestamp = models.DateTimeField(default=timezone.now)
    home_odds = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    draw_odds = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    away_odds = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    over_2_5_odds = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    under_2_5_odds = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    btts_yes_odds = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    btts_no_odds = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Odds for {self.match} @ {self.timestamp.strftime('%H:%M:%S')}"
