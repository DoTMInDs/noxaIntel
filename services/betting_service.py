from decimal import Decimal
from django.db.models import Sum
from betting.models import BetSlip, BetSelection, BettingTip
from wallet.models import Wallet

class BettingService:
    """Aggregates user wallet details, bet history, active slips, and betting tips."""

    @staticmethod
    def get_wallet_summary(user) -> dict:
        """Returns the user's wallet balance, active bets, and recent transactions overview."""
        try:
            wallet = user.wallet
            balance = wallet.balance
        except Exception:
            balance = Decimal('0.00')

        active_slips = BetSlip.objects.filter(user=user, status='SUBMITTED')
        active_count = active_slips.count()
        total_active_staked = active_slips.aggregate(total=Sum('total_stake'))['total'] or Decimal('0.00')
        total_active_payout = active_slips.aggregate(total=Sum('potential_payout'))['total'] or Decimal('0.00')

        return {
            "balance": balance,
            "active_bets_count": active_count,
            "total_active_staked": total_active_staked,
            "total_active_payout": total_active_payout
        }

    @staticmethod
    def get_active_bets(user) -> list:
        """Returns detailed summaries of the user's active bet slips."""
        slips = BetSlip.objects.filter(user=user, status='SUBMITTED').prefetch_related(
            'selections__match__home_team', 'selections__match__away_team'
        ).order_by('-created_at')
        
        result = []
        for slip in slips[:10]:  # limit to last 10
            legs = []
            for sel in slip.selections.all():
                legs.append({
                    "match": f"{sel.match.home_team.name} vs {sel.match.away_team.name}",
                    "market": sel.get_market_display(),
                    "odds": sel.odds_at_placement,
                    "result": sel.result
                })
            
            result.append({
                "id": slip.id,
                "stake": slip.total_stake,
                "odds": slip.total_odds,
                "potential_payout": slip.potential_payout,
                "type": slip.slip_type,
                "legs": legs
            })
        return result

    @staticmethod
    def get_settled_stats(user) -> dict:
        """Returns statistics for settled bets (Wins, Losses, Win Rate, ROI)."""
        slips = BetSlip.objects.filter(user=user, status__in=['WON', 'LOST'])
        total_count = slips.count()
        
        won_slips = slips.filter(status='WON')
        won_count = won_slips.count()
        lost_count = slips.filter(status='LOST').count()
        
        total_staked = slips.aggregate(total=Sum('total_stake'))['total'] or Decimal('0.00')
        total_payout = won_slips.aggregate(total=Sum('actual_payout'))['total'] or Decimal('0.00')
        
        net_profit = total_payout - total_staked
        win_rate = (won_count / total_count * 100) if total_count > 0 else 0.0
        roi = (net_profit / total_staked * 100) if total_staked > 0 else 0.0

        return {
            "total_bets": total_count,
            "won_bets": won_count,
            "lost_bets": lost_count,
            "total_staked": total_staked,
            "total_payout": total_payout,
            "net_profit": net_profit,
            "win_rate": round(win_rate, 1),
            "roi": round(roi, 1)
        }

    @staticmethod
    def get_betting_advice(tip_type: str = 'SAFE') -> list:
        """Fetches pre-generated betting recommendations from the AI (SAFE, VALUE, ACCA)."""
        tips = BettingTip.objects.filter(
            tip_type=tip_type.upper()
        ).select_related('match__home_team', 'match__away_team').order_by('-confidence_score')[:5]
        
        advice = []
        for tip in tips:
            advice.append({
                "match": f"{tip.match.home_team.name} vs {tip.match.away_team.name}",
                "description": tip.description,
                "odds": tip.odds,
                "confidence": tip.confidence_score,
                "is_vip": tip.is_vip_only
            })
        return advice
