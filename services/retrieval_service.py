import logging
from django.utils import timezone
from django.db.models import Q
from matches.models import Match, Team, League, OddsSnapshot
from predictions.models import Prediction, AIAnalysis
from services.standings_service import StandingsService
from services.player_service import PlayerService
from services.injury_service import InjuryService
from services.betting_service import BettingService

logger = logging.getLogger('ai_engine')

class RetrievalService:
    """Core RAG retrieval engine that compiles context from database and other service layers."""

    @staticmethod
    def retrieve_context(intent: str, params: dict, user) -> dict:
        """
        Assembles all relevant context based on intent and query parameters.
        Returns a context dictionary containing rich structured data.
        """
        context = {
            "intent": intent,
            "query_time": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
            "resolved_from_history": params.get("resolved_from_history", False)
        }

        teams_param = params.get("teams", [])
        player_param = params.get("player")
        league_param = params.get("league")

        # 1. Retrieve User Betting & Wallet Context if user is provided
        if user:
            context["user_wallet"] = BettingService.get_wallet_summary(user)
            if intent == 'USER_BET_ANALYSIS':
                context["user_active_bets"] = BettingService.get_active_bets(user)
                context["user_settled_stats"] = BettingService.get_settled_stats(user)

        # 2. Retrieve Team-Specific Context (Match, Odds, Prediction, Tactical, Injuries)
        if teams_param:
            context["teams_searched"] = teams_param
            
            # Find the most relevant match for these teams (Live or upcoming first, then finished)
            match = None
            if len(teams_param) == 2:
                t1, t2 = teams_param[0], teams_param[1]
                match = (
                    Match.objects.filter(
                        (Q(home_team__name__icontains=t1) & Q(away_team__name__icontains=t2)) |
                        (Q(home_team__name__icontains=t2) & Q(away_team__name__icontains=t1))
                    ).order_by('-status', 'match_date').select_related('home_team', 'away_team', 'league').first()
                )
            elif len(teams_param) == 1:
                t = teams_param[0]
                match = (
                    Match.objects.filter(
                        Q(home_team__name__icontains=t) | Q(away_team__name__icontains=t)
                    ).order_by('-status', 'match_date').select_related('home_team', 'away_team', 'league').first()
                )
            
            if match:
                context["match"] = {
                    "id": match.id,
                    "league": match.league.name,
                    "home_team": match.home_team.name,
                    "away_team": match.away_team.name,
                    "date": match.match_date.strftime("%d %b %Y %H:%M"),
                    "status": match.status,
                    "home_score": match.home_score,
                    "away_score": match.away_score,
                    "minute": match.minute
                }
                
                # Fetch Odds
                odds = match.odds_snapshots.first()
                if odds:
                    context["odds"] = {
                        "home_odds": float(odds.home_odds or 1.0),
                        "draw_odds": float(odds.draw_odds or 1.0),
                        "away_odds": float(odds.away_odds or 1.0),
                        "over_2_5_odds": float(odds.over_2_5_odds or 1.0),
                        "under_2_5_odds": float(odds.under_2_5_odds or 1.0),
                        "btts_yes_odds": float(odds.btts_yes_odds or 1.0),
                        "btts_no_odds": float(odds.btts_no_odds or 1.0),
                    }
                
                # Fetch precomputed AI Prediction
                prediction = getattr(match, 'prediction', None)
                if prediction:
                    context["prediction"] = {
                        "home_win_prob": float(prediction.home_win_prob),
                        "draw_prob": float(prediction.draw_prob),
                        "away_win_prob": float(prediction.away_win_prob),
                        "over_2_5_prob": float(prediction.over_2_5_prob),
                        "under_2_5_prob": float(prediction.under_2_5_prob),
                        "btts_yes_prob": float(prediction.btts_yes_prob),
                        "btts_no_prob": float(prediction.btts_no_prob),
                        "confidence_score": prediction.confidence_score,
                        "recommended_pick": prediction.recommended_pick,
                        "is_vip_only": prediction.is_vip_only,
                        "predicted_home_score": prediction.predicted_home_score,
                        "predicted_away_score": prediction.predicted_away_score,
                        "predicted_exact_score": prediction.predicted_exact_score
                    }
                
                # Fetch AI Analysis details
                analysis = getattr(match, 'ai_analysis', None)
                if analysis:
                    context["ai_analysis"] = {
                        "tactical_breakdown": analysis.tactical_breakdown,
                        "key_player_matchups": analysis.key_player_matchups,
                        "weather_impact": analysis.weather_impact,
                        "final_verdict": analysis.final_verdict
                    }

                # Compute head to head dynamically from database
                h2h_matches = Match.objects.filter(
                    (Q(home_team=match.home_team) & Q(away_team=match.away_team)) |
                    (Q(home_team=match.away_team) & Q(away_team=match.home_team)),
                    status='FINISHED'
                )
                h2h_stats = {"home_wins": 0, "away_wins": 0, "draws": 0, "matches_count": h2h_matches.count()}
                for hm in h2h_matches:
                    if hm.home_score is not None and hm.away_score is not None:
                        if hm.home_score > hm.away_score:
                            if hm.home_team == match.home_team:
                                h2h_stats["home_wins"] += 1
                            else:
                                h2h_stats["away_wins"] += 1
                        elif hm.home_score < hm.away_score:
                            if hm.home_team == match.away_team:
                                h2h_stats["home_wins"] += 1
                            else:
                                h2h_stats["away_wins"] += 1
                        else:
                            h2h_stats["draws"] += 1
                context["h2h_history"] = h2h_stats

            # Fetch Injury report for both teams
            for idx, team_name in enumerate(teams_param[:2]):
                key = "home_injuries" if idx == 0 else "away_injuries"
                context[key] = InjuryService.get_team_injuries(team_name)

            # Fetch player stats for searching
            if len(teams_param) > 0:
                context["team_players"] = PlayerService.get_team_key_players(teams_param[0])

        # 3. Retrieve League-Specific Context (Standings & Fixtures)
        if league_param:
            context["league_name"] = league_param
            context["league_standings"] = StandingsService.get_standings(league_param)[:10] # Top 10 standings
            context["league_fixtures"] = [
                {
                    "home": m.home_team.name,
                    "away": m.away_team.name,
                    "date": m.match_date.strftime("%d %b %H:%M"),
                    "status": m.status,
                    "score": f"{m.home_score} - {m.away_score}" if m.status in ['LIVE', 'FINISHED'] else "vs"
                } for m in Match.objects.filter(league__name__icontains=league_param, status__in=['LIVE', 'SCHEDULED'])[:5]
            ]

        # 4. Retrieve Player Specific Context
        if player_param:
            context["player_stats"] = PlayerService.get_player_stats(player_param)

        # 5. Live Match Lookup Context
        if intent == 'LIVE_MATCH_LOOKUP':
            live_matches = Match.objects.filter(status='LIVE').select_related('home_team', 'away_team', 'league')
            context["live_matches"] = [
                {
                    "home_team": lm.home_team.name,
                    "away_team": lm.away_team.name,
                    "score": f"{lm.home_score} - {lm.away_score}",
                    "minute": lm.minute,
                    "league": lm.league.name
                } for lm in live_matches
            ]

        # 6. Fixtures Lookup Context
        if intent == 'FIXTURES_LOOKUP':
            upcoming_matches = Match.objects.filter(status='SCHEDULED', kickoff_time__gte=timezone.now()).select_related('home_team', 'away_team', 'league').order_by('kickoff_time')[:10]
            if not upcoming_matches.exists():
                # fallback using match_date
                upcoming_matches = Match.objects.filter(status='SCHEDULED', match_date__gte=timezone.now()).select_related('home_team', 'away_team', 'league').order_by('match_date')[:10]
            context["upcoming_fixtures"] = [
                {
                    "home_team": um.home_team.name,
                    "away_team": um.away_team.name,
                    "date": um.match_date.strftime("%d %b %H:%M"),
                    "league": um.league.name
                } for um in upcoming_matches
            ]

        # 7. Betting Advice Context
        if intent == 'BETTING_ADVICE':
            context["safe_tips"] = BettingService.get_betting_advice('SAFE')
            context["value_tips"] = BettingService.get_betting_advice('VALUE')
            context["acca_tips"] = BettingService.get_betting_advice('ACCA')

        # 8. Standings Lookup Context
        if intent == 'STANDINGS_LOOKUP' and not league_param:
            context["league_standings"] = StandingsService.get_standings('pl')[:10] # Default to Premier League top 10

        return context
