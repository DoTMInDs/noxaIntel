from celery import shared_task
from services.football_api_service import FootballApiService
from services.odds_service import OddsService
from services.prediction_service import PredictionService

@shared_task
def sync_live_fixtures_and_odds():
    """Synchronizes live fixtures and updating odds from external API/simulation."""
    api_service = FootballApiService()
    api_service.sync_fixtures('LIVE')
    
    odds_service = OddsService()
    odds_service.sync_odds_for_all_matches()
    return "Successfully synced live matches and odds."

@shared_task
def sync_daily_fixtures():
    """Syncs daily scheduled and finished matches."""
    api_service = FootballApiService()
    api_service.sync_fixtures('SCHEDULED')
    api_service.sync_fixtures('FINISHED')
    return "Successfully synced daily fixtures."

@shared_task
def precompute_upcoming_predictions():
    """Precomputes AI probabilities and descriptions for upcoming fixtures."""
    count = PredictionService.precompute_predictions_for_upcoming()
    return f"Successfully precomputed predictions for {count} matches."

@shared_task
def refresh_match_prediction(match_id):
    """Refreshes a specific match's predictions when cache misses."""
    from matches.models import Match
    try:
        match = Match.objects.get(id=match_id)
        PredictionService.generate_prediction(match)
        return f"Refreshed prediction for match {match_id}."
    except Match.DoesNotExist:
        return f"Match {match_id} does not exist."

