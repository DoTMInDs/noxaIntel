from django.db import models
from matches.models import Match


class BettingTip(models.Model):
    TIP_TYPE_CHOICES = [
        ('SAFE', 'Safe Bet'),
        ('VALUE', 'Value Bet'),
        ('ACCA', 'Accumulator'),
    ]

    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='betting_tips')
    tip_type = models.CharField(max_length=20, choices=TIP_TYPE_CHOICES, default='SAFE')
    odds = models.DecimalField(max_digits=5, decimal_places=2)
    confidence_score = models.IntegerField(help_text="0-100 scale")
    description = models.TextField()
    is_vip_only = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-confidence_score', '-created_at']
        indexes = [
            models.Index(fields=['tip_type', 'is_vip_only']),
        ]

    def __str__(self):
        return f"{self.get_tip_type_display()} for {self.match} (@ {self.odds})"
