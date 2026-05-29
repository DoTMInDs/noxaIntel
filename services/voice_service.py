import logging
from matches.models import Match
from betting.models import BettingTip
from predictions.models import Prediction
from django.utils import timezone
from services.prediction_service import PredictionService

logger = logging.getLogger('ai_engine')

class VoiceService:
    """Interprets browser-transcribed speech queries and outputs actions or textual responses."""

    @staticmethod
    def parse_voice_command(speech_text, user):
        """Maps user spoken query to a structured natural-language response.
        
        Supports:
          - 'safe' / 'safest bets'
          - 'live' / 'show live matches'
          - 'analyze [team1] vs [team2]'
          - 'high confidence' / 'vip'
        """
        query = speech_text.strip().lower()
        logger.info(f"Processing voice query from {user.username}: '{query}'")

        # 1. Safest Bets
        if 'safe' in query or 'safest' in query or 'best bet' in query:
            safe_tips = BettingTip.objects.filter(tip_type='SAFE').select_related('match__home_team', 'match__away_team')[:4]
            if not safe_tips.exists():
                return "I couldn't find any precalculated safe bets at this moment. Let me trigger a quick system refresh."
            
            response = "Here are the safest AI-recommended bets for you:\n"
            for tip in safe_tips:
                response += f"• {tip.match.home_team.name} vs {tip.match.away_team.name}: {tip.description} (Odds: {tip.odds})\n"
            return response

        # 2. Live Matches
        if 'live' in query or 'in play' in query or 'current matches' in query:
            live_matches = Match.objects.filter(status='LIVE').select_related('home_team', 'away_team')
            if not live_matches.exists():
                return "There are no matches currently playing live. Check upcoming scheduled fixtures!"
            
            response = f"We have {live_matches.count()} live matches in progress:\n"
            for m in live_matches:
                score_str = f"{m.home_score} - {m.away_score}" if m.home_score is not None else "0 - 0"
                response += f"• {m.home_team.name} vs {m.away_team.name} ({m.minute or 'Live'}): Score is {score_str}\n"
            return response

        # 3. High-Confidence / VIP recommendations
        if 'high confidence' in query or 'confidence' in query or 'vip' in query or 'premium' in query:
            # Check user subscription
            is_vip = getattr(user, 'profile', None) and user.profile.subscription_tier.name in ['Premium', 'VIP']
            
            predictions = Prediction.objects.filter(confidence_score__gte=80).select_related('match__home_team', 'match__away_team')[:4]
            if not predictions.exists():
                return "No high confidence predictions are currently ready. Check back in a few minutes!"
                
            response = "Here are our highest-confidence match models:\n"
            for pred in predictions:
                if pred.is_vip_only and not is_vip:
                    response += f"• {pred.match.home_team.name} vs {pred.match.away_team.name}: 🔒 [VIP Access Only - Upgrade Profile]\n"
                else:
                    response += f"• {pred.match.home_team.name} vs {pred.match.away_team.name}: {pred.recommended_pick} (Confidence: {pred.confidence_score}%)\n"
            return response

        # 4. Analyze Match (e.g., 'analyze Arsenal vs Chelsea')
        if 'analyze' in query or 'vs' in query or 'versus' in query:
            # Try to identify team names in query
            teams = Team_Identifier.extract_teams_from_query(query)
            if teams:
                team1, team2 = teams
                match = Match.objects.filter(
                    home_team__name__icontains=team1,
                    away_team__name__icontains=team2
                ).first() or Match.objects.filter(
                    home_team__name__icontains=team2,
                    away_team__name__icontains=team1
                ).first()

                if match:
                    # Sync predictions if it does not exist
                    prediction = getattr(match, 'prediction', None)
                    if not prediction:
                        prediction = PredictionService.generate_prediction(match)
                        
                    analysis = getattr(match, 'ai_analysis', None)
                    
                    response = f"AI Match Analysis for {match.home_team.name} vs {match.away_team.name}:\n"
                    response += f"• Win Probabilities: {match.home_team.name} ({prediction.home_win_prob}%), Draw ({prediction.draw_prob}%), {match.away_team.name} ({prediction.away_win_prob}%)\n"
                    response += f"• Suggested Bet: {prediction.recommended_pick} (Confidence: {prediction.confidence_score}%)\n"
                    if analysis:
                        response += f"• Verdict: {analysis.final_verdict}\n"
                    return response
                else:
                    return f"I found references to {team1} and {team2}, but no corresponding scheduled fixture was found in our dashboard database."

        # Default conversational query fallback
        return (
            "I heard you! Try asking specific questions like:\n"
            "• 'What are the safest bets?'\n"
            "• 'Show live matches'\n"
            "• 'Analyze Arsenal vs Chelsea'\n"
            "• 'Give me high confidence predictions'"
        )

class Team_Identifier:
    """Helper class to find teams in a voice query string."""
    
    @staticmethod
    def extract_teams_from_query(query):
        # List of all team names/substrings to search for
        team_names = [
            "arsenal", "manchester city", "city", "liverpool", "chelsea",
            "barcelona", "real madrid", "madrid", "atletico", "sevilla",
            "bayern", "dortmund", "leipzig", "leverkusen",
            "inter", "milan", "juventus", "napoli",
            "psg", "marseille", "lyon", "monaco"
        ]
        
        found = []
        for name in team_names:
            if name in query:
                # Map shorthand names
                mapped = name
                if name == "city": mapped = "manchester city"
                if name == "madrid": mapped = "real madrid"
                found.append(mapped)
                if len(found) == 2:
                    return found
        if len(found) == 1:
            # Try to split by 'vs' or 'versus' to find the other team
            parts = query.split('vs') if 'vs' in query else query.split('versus')
            if len(parts) == 2:
                # Return the found team, plus the other segment clean
                other_part = parts[1].strip() if found[0] in parts[0] else parts[0].strip()
                # Clean up query verbs
                other_part = other_part.replace("analyze", "").replace("show", "").strip()
                return [found[0], other_part]
        return None
