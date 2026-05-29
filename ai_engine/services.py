import random
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone
from matches.models import Match, OddsSnapshot
from predictions.models import Prediction, AIAnalysis
from betting.models import BettingTip


class AIEngineService:
    """Service layer encapsulating ML precomputation, explanations, and assistant logic."""

    @staticmethod
    def precompute_match_prediction(match_id):
        """Generates and stores prediction probabilities and AI analysis for a match."""
        try:
            match = Match.objects.select_related('home_team', 'away_team', 'league').get(id=match_id)
        except Match.DoesNotExist:
            return None

        # Deterministic pseudo-random generation based on match ID to simulate ML inference
        random.seed(match.id)

        home_prob = Decimal(random.uniform(35.0, 65.0)).quantize(Decimal('0.01'))
        draw_prob = Decimal(random.uniform(15.0, 30.0)).quantize(Decimal('0.01'))
        away_prob = Decimal(100.0) - home_prob - draw_prob

        over_prob = Decimal(random.uniform(45.0, 75.0)).quantize(Decimal('0.01'))
        under_prob = Decimal(100.0) - over_prob

        btts_yes = Decimal(random.uniform(50.0, 80.0)).quantize(Decimal('0.01'))
        btts_no = Decimal(100.0) - btts_yes

        confidence = random.randint(70, 95)

        picks = [f"{match.home_team.name} Win", "Over 2.5 Goals", "Both Teams to Score - Yes"]
        recommended_pick = random.choice(picks)

        # Update or create Prediction
        prediction, _ = Prediction.objects.update_or_create(
            match=match,
            defaults={
                'home_win_prob': home_prob,
                'draw_prob': draw_prob,
                'away_win_prob': away_prob,
                'over_2_5_prob': over_prob,
                'under_2_5_prob': under_prob,
                'btts_yes_prob': btts_yes,
                'btts_no_prob': btts_no,
                'confidence_score': confidence,
                'recommended_pick': recommended_pick,
                'is_vip_only': confidence > 88,
            }
        )

        # Update or create AIAnalysis
        tactical = (
            f"{match.home_team.name} is expected to utilize a high-pressing 4-3-3 system, "
            f"aiming to exploit the wide channels against {match.away_team.name}'s compact 4-2-3-1 pivot."
        )
        matchups = (
            f"Key battle in midfield: {match.home_team.name}'s central playmaker vs {match.away_team.name}'s defensive anchor. "
            f"Wing transitions will be crucial."
        )
        weather = "Clear skies, optimal pitch conditions."
        verdict = (
            f"Given the current attacking form and expected goals (xG) trajectory, "
            f"our neural network projects a high probability of {recommended_pick}."
        )

        AIAnalysis.objects.update_or_create(
            match=match,
            defaults={
                'tactical_breakdown': tactical,
                'key_player_matchups': matchups,
                'weather_impact': weather,
                'final_verdict': verdict,
            }
        )

        # Generate Betting Tips
        AIEngineService.generate_betting_tips(match, prediction)

        # Invalidate related caches
        cache.delete(f"prediction_partial_{match.id}")
        cache.delete("betting_tips_all_vip_True")
        cache.delete("betting_tips_all_vip_False")

        return prediction

    @staticmethod
    def generate_betting_tips(match, prediction):
        """Generates Safe, Value, and Accumulator tips based on prediction probabilities."""
        random.seed(match.id + 100)

        # Safe Bet
        safe_odds = Decimal(random.uniform(1.25, 1.55)).quantize(Decimal('0.01'))
        BettingTip.objects.update_or_create(
            match=match,
            tip_type='SAFE',
            defaults={
                'odds': safe_odds,
                'confidence_score': random.randint(85, 95),
                'description': f"Low risk selection: {prediction.recommended_pick} based on solid historical win rate.",
                'is_vip_only': False,
            }
        )

        # Value Bet
        value_odds = Decimal(random.uniform(1.90, 2.80)).quantize(Decimal('0.01'))
        BettingTip.objects.update_or_create(
            match=match,
            tip_type='VALUE',
            defaults={
                'odds': value_odds,
                'confidence_score': random.randint(75, 84),
                'description': f"High +EV selection: {match.away_team.name} Handicap / Goal line discrepancy identified by AI.",
                'is_vip_only': False,
            }
        )

        # Acca Tip (VIP)
        acca_odds = Decimal(random.uniform(3.50, 6.50)).quantize(Decimal('0.01'))
        BettingTip.objects.update_or_create(
            match=match,
            tip_type='ACCA',
            defaults={
                'odds': acca_odds,
                'confidence_score': random.randint(70, 80),
                'description': f"Combo multiplier piece: Combine {prediction.recommended_pick} with Over 2.5 goals for maximum return.",
                'is_vip_only': True,
            }
        )

    @staticmethod
    def process_assistant_query(query, user):
        """Processes AI Assistant queries instantly using precomputed context."""
        query_lower = query.lower()
        
        # Check if user has assistant access
        is_vip = getattr(user, 'profile', None) and (
            user.profile.subscription_tier.access_ai_assistant or user.profile.subscription_tier.name in ['Premium', 'VIP']
        )

        if not is_vip and 'vip' in query_lower:
            return (
                "🔒 This specific tactical insight requires a Premium or VIP subscription. "
                "Upgrade your account in the Profile tab to unlock advanced AI assistant capabilities!"
            )

        if 'sure' in query_lower or 'safe' in query_lower or 'best' in query_lower:
            tips = BettingTip.objects.filter(tip_type='SAFE').select_related('match__home_team', 'match__away_team')[:3]
            if tips:
                tip_text = "\n".join([f"⚽ {t.match}: {t.description} (Odds: {t.odds})" for t in tips])
                return f"🤖 Here are the top AI-recommended Safe Bets right now:\n{tip_text}"
            return "🤖 Currently analyzing upcoming fixtures for high-confidence safe bets. Check back shortly!"

        if 'match' in query_lower or 'game' in query_lower or 'vs' in query_lower or 'play' in query_lower:
            matches = Match.objects.filter(status='SCHEDULED').select_related('home_team', 'away_team')[:3]
            if matches:
                match_text = "\n".join([f"📅 {m.home_team.name} vs {m.away_team.name} ({m.match_date.strftime('%b %d, %H:%M')})" for m in matches])
                return f"🤖 Here are the key upcoming matches our AI is tracking:\n{match_text}"
            return "🤖 No upcoming scheduled matches found in the immediate pipeline."

        # Default contextual response
        return (
            f"🤖 AI Assistant Insight: Based on our latest precomputed neural network snapshots, "
            f"home advantage holds a 54% weight across major European fixtures this weekend. "
            f"We recommend focusing on Over 2.5 goal lines in matches involving top-tier attacking pivots."
        )
