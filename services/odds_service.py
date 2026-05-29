import os
import json
import urllib.request
from decimal import Decimal
import random
from django.utils import timezone
from matches.models import Match, OddsSnapshot
from services.cache_service import CacheService

class OddsService:
    """Service to fetch live/upcoming betting odds from The Odds API or generate simulated odds."""

    def __init__(self):
        self.api_key = os.getenv('ODDS_API_KEY')

    def sync_odds_for_all_matches(self):
        """Celery task entry point to update odds for live/upcoming matches."""
        matches = Match.objects.filter(status__in=['LIVE', 'SCHEDULED'])
        
        if self.api_key:
            self._fetch_and_save_real_odds(matches)
        else:
            self._generate_simulated_odds(matches)

    def _fetch_and_save_real_odds(self, matches):
        """Fetches from The Odds API (e.g., EPL, La Liga)."""
        # EPL odds fetch as a default demonstration
        url = f"https://api.the-odds-api.com/v4/sports/soccer_epl/odds/?apiKey={self.api_key}&regions=eu&markets=h2h,totals"
        
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as response:
                odds_data = json.loads(response.read().decode())
                self._parse_and_store_odds_api(odds_data, matches)
        except Exception as e:
            print(f"Error calling The Odds API: {e}")
            # Fail gracefully by falling back to simulation if real fetch fails
            self._generate_simulated_odds(matches)

    def _parse_and_store_odds_api(self, odds_data, matches):
        """Correlates Odds API outcomes with local matches and saves snapshots."""
        for game in odds_data:
            home_name = game['home_team']
            away_name = game['away_team']
            
            # Match finding (fuzzy check or name checking)
            matching_matches = matches.filter(
                home_team__name__icontains=home_name[:5],
                away_team__name__icontains=away_name[:5]
            )
            
            if not matching_matches.exists():
                continue
                
            match = matching_matches.first()
            
            # Default fallback odds
            home_odds, draw_odds, away_odds = Decimal('2.00'), Decimal('3.20'), Decimal('3.50')
            over_odds, under_odds = Decimal('1.85'), Decimal('1.95')
            btts_yes, btts_no = Decimal('1.70'), Decimal('2.10')
            
            # Process markets
            for bookmaker in game.get('bookmakers', []):
                # Use the first available bookmaker (usually popular European bookies)
                for market in bookmaker.get('markets', []):
                    if market['key'] == 'h2h':
                        for outcome in market['outcomes']:
                            if outcome['name'] == home_name:
                                home_odds = Decimal(str(outcome['price']))
                            elif outcome['name'] == away_name:
                                away_odds = Decimal(str(outcome['price']))
                            else:
                                draw_odds = Decimal(str(outcome['price']))
                    elif market['key'] == 'totals':
                        for outcome in market['outcomes']:
                            if outcome.get('point') == 2.5:
                                if outcome['name'].lower() == 'over':
                                    over_odds = Decimal(str(outcome['price']))
                                else:
                                    under_odds = Decimal(str(outcome['price']))
                    elif market['key'] == 'btts':
                        for outcome in market['outcomes']:
                            if outcome['name'].lower() == 'yes':
                                btts_yes = Decimal(str(outcome['price']))
                            else:
                                btts_no = Decimal(str(outcome['price']))
                break  # Just use the first bookmaker for consistency
                
            OddsSnapshot.objects.create(
                match=match,
                home_odds=home_odds,
                draw_odds=draw_odds,
                away_odds=away_odds,
                over_2_5_odds=over_odds,
                under_2_5_odds=under_odds,
                btts_yes_odds=btts_yes,
                btts_no_odds=btts_no
            )
            CacheService.invalidate_match(match.id)

    def _generate_simulated_odds(self, matches):
        """Generates realistic odds that fluctuate over time based on team names & seed."""
        for match in matches:
            minute_seed = 0
            if match.minute:
                try:
                    digits = ''.join(c for c in match.minute if c.isdigit())
                    if digits:
                        minute_seed = int(digits)
                except ValueError:
                    pass
            random.seed(match.id + minute_seed + int(timezone.now().timestamp() // 120))
            
            # Basic power ratings simulation
            home_fav = len(match.home_team.name) % 2 == 0
            
            if home_fav:
                home_odds = Decimal(str(round(random.uniform(1.35, 1.95), 2)))
                away_odds = Decimal(str(round(random.uniform(3.50, 6.00), 2)))
            else:
                home_odds = Decimal(str(round(random.uniform(2.80, 4.50), 2)))
                away_odds = Decimal(str(round(random.uniform(1.70, 2.50), 2)))
                
            draw_odds = Decimal(str(round(random.uniform(3.10, 3.80), 2)))
            
            over_odds = Decimal(str(round(random.uniform(1.65, 2.45), 2)))
            under_odds = Decimal(str(round(random.uniform(1.55, 2.25), 2)))
            
            btts_yes = Decimal(str(round(random.uniform(1.50, 2.10), 2)))
            btts_no = Decimal(str(round(random.uniform(1.75, 2.40), 2)))
            
            OddsSnapshot.objects.create(
                match=match,
                home_odds=home_odds,
                draw_odds=draw_odds,
                away_odds=away_odds,
                over_2_5_odds=over_odds,
                under_2_5_odds=under_odds,
                btts_yes_odds=btts_yes,
                btts_no_odds=btts_no
            )
            CacheService.invalidate_match(match.id)
