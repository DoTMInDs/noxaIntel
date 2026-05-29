from django.core.management.base import BaseCommand
from services.football_api_service import FootballApiService
from services.odds_service import OddsService
from services.prediction_service import PredictionService

class Command(BaseCommand):
    help = 'Manually synchronizes football matches, live odds, and precomputes AI predictions.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('[*] Initializing platform data synchronization...'))
        
        # 1. Sync leagues, teams, and matches
        self.stdout.write('--> Syncing leagues, teams, and match fixtures...')
        api_service = FootballApiService()
        api_service.sync_all_data()
        self.stdout.write(self.style.SUCCESS('[OK] Matches synchronized.'))

        # 2. Sync Odds
        self.stdout.write('--> Fetching and updating live odds snapshots...')
        odds_service = OddsService()
        odds_service.sync_odds_for_all_matches()
        self.stdout.write(self.style.SUCCESS('[OK] Betting odds updated.'))

        # 3. Precompute Predictions
        self.stdout.write('--> Precomputing AI predictions for scheduled fixtures...')
        count = PredictionService.precompute_predictions_for_upcoming()
        self.stdout.write(self.style.SUCCESS(f'[OK] {count} predictions generated and cached.'))

        self.stdout.write(self.style.SUCCESS('[DONE] Full system synchronization complete!'))
