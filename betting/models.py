from django.db import models
from django.conf import settings
from django.utils import timezone
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


class BetSlip(models.Model):
    STATUS_CHOICES = [
        ('SUBMITTED', 'Submitted'),
        ('WON', 'Won'),
        ('LOST', 'Lost'),
        ('VOID', 'Void'),
        ('CASHOUT', 'Cashed Out'),
    ]

    SLIP_TYPE_CHOICES = [
        ('SINGLE', 'Single'),
        ('ACCUMULATOR', 'Accumulator'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bet_slips',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUBMITTED')
    slip_type = models.CharField(max_length=20, choices=SLIP_TYPE_CHOICES, default='SINGLE')
    total_stake = models.DecimalField(max_digits=12, decimal_places=2)
    total_odds = models.DecimalField(max_digits=8, decimal_places=2)
    potential_payout = models.DecimalField(max_digits=12, decimal_places=2)
    actual_payout = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    transaction = models.OneToOneField(
        'wallet.Transaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bet_slip',
    )
    created_at = models.DateTimeField(default=timezone.now)
    settled_at = models.DateTimeField(null=True, blank=True)
    
    # Early payout (Cash Out) support
    is_cashed_out = models.BooleanField(default=False)
    cash_out_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"Slip #{self.pk} — {self.slip_type} ({self.status}) — GHS {self.total_stake}"

    @property
    def is_settled(self):
        return self.status in ['WON', 'LOST', 'VOID', 'CASHOUT']

    def calculate_cash_out_value(self) -> float:
        """
        Dynamically calculate early payout cash-out value.
        For simplicity and robustness:
        - If any leg has already lost, cash out value is 0.
        - If the bet is already settled, cash out is 0.
        - Otherwise, we calculate a fair cash-out value:
          We can sum up the progress. For example, if there are multiple legs,
          we look at the completed won legs vs pending legs.
          A simple robust formula is:
            75% of (stake * odds_of_resolved_won_legs) for accumulated risk.
          If all legs are still pending, we offer 85% of the stake as a safety cash-out.
        """
        if self.is_settled:
            return 0.00

        selections = self.selections.all()
        resolved_won_odds = 1.00
        has_lost = False
        pending_count = 0
        won_count = 0

        for sel in selections:
            if sel.result == 'LOST':
                has_lost = True
            elif sel.result == 'WON':
                resolved_won_odds *= float(sel.odds_at_placement)
                won_count += 1
            else:
                pending_count += 1

        if has_lost:
            return 0.00

        # Simple algorithm:
        # If all resolved legs won, offer cashout:
        # value = stake * (resolved_won_odds) * (0.90 ^ pending_count) * 0.85
        # Example: 10 GHS bet, 1 leg won at 2.0 odds, 1 leg pending:
        # value = 10 * 2.0 * 0.9 * 0.85 = 15.3 GHS.
        stake = float(self.total_stake)
        
        # Apply a fee / discount factor
        if won_count == 0:
            # 85% of stake if no legs have resolved yet
            value = stake * 0.85
        else:
            value = stake * resolved_won_odds * (0.88 ** pending_count)

        # Cap it at 95% of potential payout, and minimum at 10% of stake
        max_value = float(self.potential_payout) * 0.95
        min_value = stake * 0.10
        value = min(max(value, min_value), max_value)

        return round(value, 2)


class BetSelection(models.Model):
    MARKET_CHOICES = [
        ('HOME_WIN', 'Home Win (1)'),
        ('DRAW', 'Draw (X)'),
        ('AWAY_WIN', 'Away Win (2)'),
        ('OVER_2_5', 'Over 2.5'),
        ('UNDER_2_5', 'Under 2.5'),
        ('BTTS_YES', 'BTTS Yes'),
        ('BTTS_NO', 'BTTS No'),
    ]

    RESULT_CHOICES = [
        ('PENDING', 'Pending'),
        ('WON', 'Won'),
        ('LOST', 'Lost'),
        ('VOID', 'Void'),
    ]

    bet_slip = models.ForeignKey(
        BetSlip,
        on_delete=models.CASCADE,
        related_name='selections',
    )
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name='bet_selections',
    )
    market = models.CharField(max_length=20, choices=MARKET_CHOICES)
    odds_at_placement = models.DecimalField(max_digits=6, decimal_places=2)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default='PENDING')

    def __str__(self):
        return f"Selection: {self.match} — {self.get_market_display()} @ {self.odds_at_placement} ({self.result})"

