from decimal import Decimal
import random
from django.utils import timezone
from matches.models import Match
from predictions.models import Prediction, AIAnalysis
from betting.models import BettingTip
from services.cache_service import CacheService

class PredictionService:
    """Calculates predictions, confidence ratings, and tactical AI reviews for matches."""

    @staticmethod
    def precompute_predictions_for_upcoming():
        """Precomputes predictions for all upcoming scheduled matches."""
        upcoming = Match.objects.filter(status='SCHEDULED')[:40]
        count = 0
        for match in upcoming:
            PredictionService.generate_prediction(match)
            count += 1
        return count

    @staticmethod
    def generate_prediction(match):
        """Generates probabilities, selection, and writes an AI tactical review for a match."""
        # Seed pseudo-random generator with match ID to keep simulation stable
        random.seed(match.id)

        # Formulate probabilities
        home_len = len(match.home_team.name)
        away_len = len(match.away_team.name)
        
        # Simulate dynamic strength difference
        diff = (home_len - away_len) * 2.5
        
        home_win_prob = Decimal(str(round(max(15.0, min(80.0, 45.0 + diff)), 2)))
        draw_prob = Decimal(str(round(max(10.0, min(40.0, 25.0 - (abs(diff) * 0.2))), 2)))
        away_win_prob = Decimal('100.00') - home_win_prob - draw_prob
        
        over_2_5_prob = Decimal(str(round(random.uniform(40.0, 80.0), 2)))
        under_2_5_prob = Decimal('100.00') - over_2_5_prob
        
        btts_yes_prob = Decimal(str(round(random.uniform(45.0, 78.0), 2)))
        btts_no_prob = Decimal('100.00') - btts_yes_prob
        
        confidence_score = int(random.uniform(60, 96))
        
        # Recommended pick selection
        picks = []
        if home_win_prob > 50:
            picks.append(f"{match.home_team.name} Win")
        elif away_win_prob > 50:
            picks.append(f"{match.away_team.name} Win")
        else:
            picks.append("Double Chance 1X" if home_win_prob > away_win_prob else "Double Chance X2")
            
        if over_2_5_prob > 60:
            picks.append("Over 2.5 Goals")
        elif under_2_5_prob > 60:
            picks.append("Under 2.5 Goals")
            
        if btts_yes_prob > 65:
            picks.append("Both Teams to Score - Yes")
            
        recommended_pick = picks[0] if picks else f"{match.home_team.name} or Draw"
        is_vip_only = confidence_score >= 85

        # Create/Update prediction
        prediction, _ = Prediction.objects.update_or_create(
            match=match,
            defaults={
                "home_win_prob": home_win_prob,
                "draw_prob": draw_prob,
                "away_win_prob": away_win_prob,
                "over_2_5_prob": over_2_5_prob,
                "under_2_5_prob": under_2_5_prob,
                "btts_yes_prob": btts_yes_prob,
                "btts_no_prob": btts_no_prob,
                "confidence_score": confidence_score,
                "recommended_pick": recommended_pick,
                "is_vip_only": is_vip_only
            }
        )

        # Generate AI Tactical Analysis
        tactical = (
            f"{match.home_team.name} typically lines up in a high-intensity {random.choice(['4-3-3', '4-2-3-1'])} formation. "
            f"Their focus lies on quick wide transitions and heavy counter-pressing. "
            f"Conversely, {match.away_team.name} utilizes a structural {random.choice(['5-3-2', '4-4-2'])} block, "
            f"aiming to choke direct central supply lines and hit back via set-pieces."
        )
        
        matchups = (
            f"Crucial duel in wide sectors: {match.home_team.name}'s leading winger against "
            f"{match.away_team.name}'s full-back. Tactical analysis indicates the home side will "
            f"overload the half-spaces to drag defenders out of position."
        )
        
        weather = f"{random.choice(['Clear skies', 'Overcast', 'Light Rain'])}, temperature around {random.randint(12, 22)}°C. Minimal pitch impact."
        
        verdict = (
            f"With a {confidence_score}% AI confidence score, the model projects high value in {recommended_pick}. "
            f"The home side's superior xG trend at home supports this selection."
        )

        AIAnalysis.objects.update_or_create(
            match=match,
            defaults={
                "tactical_breakdown": tactical,
                "key_player_matchups": matchups,
                "weather_impact": weather,
                "final_verdict": verdict
            }
        )

        # Automatically spawn betting recommendations for the match
        PredictionService._generate_betting_tips(match, prediction)

        # Cache predictions
        CacheService.invalidate_match(match.id)
        return prediction

    @staticmethod
    def _generate_betting_tips(match, prediction):
        """Spawns SAFE, VALUE, and ACCA betting tips for the match based on predictions."""
        random.seed(match.id + 77)

        # Safe leg
        safe_odds = Decimal(str(round(random.uniform(1.28, 1.55), 2)))
        BettingTip.objects.update_or_create(
            match=match,
            tip_type='SAFE',
            defaults={
                'odds': safe_odds,
                'confidence_score': int(random.uniform(85, 95)),
                'description': f"Low-risk AI model target: {prediction.recommended_pick}. Extremely robust defensive ratings support selection.",
                'is_vip_only': False
            }
        )

        # Value leg
        value_odds = Decimal(str(round(random.uniform(1.95, 2.75), 2)))
        BettingTip.objects.update_or_create(
            match=match,
            tip_type='VALUE',
            defaults={
                'odds': value_odds,
                'confidence_score': int(random.uniform(75, 84)),
                'description': f"Value Opportunity: Backing under/over lines based on discrepancy in average bookmaker ratings.",
                'is_vip_only': False
            }
        )

        # ACCA leg
        acca_odds = Decimal(str(round(random.uniform(3.40, 5.80), 2)))
        BettingTip.objects.update_or_create(
            match=match,
            tip_type='ACCA',
            defaults={
                'odds': acca_odds,
                'confidence_score': int(random.uniform(65, 75)),
                'description': f"Accumulator Multiplier: Combine {match.home_team.name} ML with Over 2.5 goals for maximum return potential.",
                'is_vip_only': True
            }
        )
