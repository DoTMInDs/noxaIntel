import os
import json
import urllib.request
from datetime import datetime, timedelta
from decimal import Decimal
import random
from django.utils import timezone
from django.conf import settings
from matches.models import League, Team, Match, OddsSnapshot
from services.cache_service import CacheService

class FootballApiService:
    """Ingests football fixtures, standings, and team stats from external APIs or mock fallbacks."""

    def __init__(self):
        self.api_football_key = os.getenv('API_FOOTBALL_KEY')
        self.football_data_key = os.getenv('FOOTBALL_DATA_ORG_KEY')

    def sync_all_data(self):
        """Main synchronizer run by Celery task."""
        # 1. Sync Leagues and Teams
        self.sync_leagues_and_teams()
        
        # 2. Sync Fixtures (Live, Scheduled, Finished)
        self.sync_fixtures('LIVE')
        self.sync_fixtures('SCHEDULED')
        self.sync_fixtures('FINISHED')

    def sync_leagues_and_teams(self):
        """Ensures fundamental leagues and teams exist in the database."""
        # Standard leagues we operate on
        leagues_def = [
            {"name": "Premier League", "country": "England", "code": "PL"},
            {"name": "La Liga", "country": "Spain", "code": "LL"},
            {"name": "Bundesliga", "country": "Germany", "code": "BL"},
            {"name": "Serie A", "country": "Italy", "code": "SA"},
            {"name": "Ligue 1", "country": "France", "code": "L1"},
        ]
        
        leagues = {}
        for l in leagues_def:
            obj, _ = League.objects.update_or_create(code=l["code"], defaults=l)
            leagues[l["code"]] = obj

        teams_def = {
            "PL": [("Arsenal", "ARS"), ("Manchester City", "MCI"), ("Liverpool", "LIV"), ("Chelsea", "CHE")],
            "LL": [("Barcelona", "BAR"), ("Real Madrid", "RMA"), ("Atletico Madrid", "ATM"), ("Sevilla", "SEV")],
            "BL": [("Bayern Munich", "BAY"), ("Borussia Dortmund", "BVB"), ("RB Leipzig", "RBL"), ("Leverkusen", "LEV")],
            "SA": [("Inter Milan", "INT"), ("AC Milan", "ACM"), ("Juventus", "JUV"), ("Napoli", "NAP")],
            "L1": [("PSG", "PSG"), ("Marseille", "MAR"), ("Lyon", "LYO"), ("Monaco", "MON")],
        }

        for code, team_list in teams_def.items():
            league = leagues[code]
            for name, team_code in team_list:
                Team.objects.update_or_create(
                    code=team_code,
                    defaults={
                        "name": name,
                        "league": league,
                        "logo_url": f"https://img.icons8.com/color/48/000000/{name.lower().replace(' ', '-')}.png"
                    }
                )

    def sync_fixtures(self, status):
        """Fetches fixtures for the given status and saves them to the DB with fallback."""
        success = False

        # 1. Try API-Football (RapidAPI or API-Sports)
        if self.api_football_key:
            try:
                data = self._fetch_from_api_football(status)
                if data and 'response' in data and data['response']:
                    self._save_api_football_data(data)
                    success = True
            except Exception as e:
                print(f"Failed to sync via API-Football: {e}")

        # 2. Try Football-Data.org if first failed or not configured
        if not success and self.football_data_key:
            try:
                data = self._fetch_from_football_data_org(status)
                if data and 'matches' in data and data['matches']:
                    self._save_football_data_org_data(data)
                    success = True
            except Exception as e:
                print(f"Failed to sync via Football-Data.org: {e}")

        # 3. Fallback to simulation if both failed/not configured
        if not success:
            print(f"Using simulated fixtures fallback for status: {status}")
            self._generate_mock_fixtures(status)

    def _fetch_from_api_football(self, status):
        """Queries API-Football API (either direct API-Sports or via RapidAPI)."""
        is_direct = len(self.api_football_key) == 32

        if is_direct:
            url = "https://v3.football.api-sports.io/fixtures?"
        else:
            url = "https://api-football-v1.p.rapidapi.com/v3/fixtures?"

        if status == 'LIVE':
            url += "live=all"
        else:
            # Get matches for today +/- 3 days
            date_str = timezone.now().strftime('%Y-%m-%d')
            url += f"date={date_str}"

        req = urllib.request.Request(url)
        if is_direct:
            req.add_header("x-apisports-key", self.api_football_key)
        else:
            req.add_header("X-RapidAPI-Key", self.api_football_key)
            req.add_header("X-RapidAPI-Host", "api-football-v1.p.rapidapi.com")

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            print(f"Error querying API-Football: {e}")
            return None

    def _save_api_football_data(self, data):
        """Parses and stores API-Football JSON response in the database."""
        if not data or 'response' not in data:
            return
        
        for item in data['response']:
            fixture = item['fixture']
            teams = item['teams']
            goals = item['goals']
            league_data = item['league']
            
            # Map statuses
            api_status = fixture['status']['short']
            status_map = {
                'TBD': 'SCHEDULED', 'NS': 'SCHEDULED',
                '1H': 'LIVE', 'HT': 'LIVE', '2H': 'LIVE', 'ET': 'LIVE', 'P': 'LIVE',
                'FT': 'FINISHED', 'AET': 'FINISHED', 'PEN': 'FINISHED',
                'PST': 'POSTPONED'
            }
            db_status = status_map.get(api_status, 'SCHEDULED')
            
            # Get or create League and Teams
            league, _ = League.objects.update_or_create(
                code=str(league_data['id'])[:10],
                defaults={
                    "name": league_data['name'],
                    "country": league_data.get('country', 'International'),
                    "logo_url": league_data.get('logo')
                }
            )
            
            home_team, _ = Team.objects.update_or_create(
                code=str(teams['home']['id'])[:10],
                defaults={
                    "name": teams['home']['name'],
                    "league": league,
                    "logo_url": teams['home'].get('logo')
                }
            )
            
            away_team, _ = Team.objects.update_or_create(
                code=str(teams['away']['id'])[:10],
                defaults={
                    "name": teams['away']['name'],
                    "league": league,
                    "logo_url": teams['away'].get('logo')
                }
            )
            
            match_date = datetime.fromisoformat(fixture['date'].replace('Z', '+00:00'))
            
            match, created = Match.objects.update_or_create(
                id=fixture['id'],
                defaults={
                    "league": league,
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_date": match_date,
                    "status": db_status,
                    "home_score": goals.get('home'),
                    "away_score": goals.get('away'),
                    "minute": f"{fixture['status'].get('elapsed') or ''}'" if db_status == 'LIVE' else ('FT' if db_status == 'FINISHED' else None)
                }
            )
            CacheService.invalidate_match(match.id)

    def _fetch_from_football_data_org(self, status):
        """Queries Football-Data.org API."""
        url = "https://api.football-data.org/v4/matches"
        if status == 'LIVE':
            url += "?status=LIVE"
            
        req = urllib.request.Request(url)
        req.add_header("X-Auth-Token", self.football_data_key)
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            print(f"Error querying Football-Data.org: {e}")
            return None

    def _save_football_data_org_data(self, data):
        """Parses and stores Football-Data.org JSON in DB."""
        if not data or 'matches' not in data:
            return
            
        for m in data['matches']:
            # Map status
            api_status = m['status']
            status_map = {
                'TIMED': 'SCHEDULED', 'SCHEDULED': 'SCHEDULED',
                'IN_PLAY': 'LIVE', 'PAUSED': 'LIVE',
                'FINISHED': 'FINISHED', 'POSTPONED': 'POSTPONED'
            }
            db_status = status_map.get(api_status, 'SCHEDULED')
            
            # Get or create League and Teams
            comp = m['competition']
            league, _ = League.objects.update_or_create(
                code=comp['code'],
                defaults={
                    "name": comp['name'],
                    "country": comp.get('area', {}).get('name', 'Europe'),
                    "logo_url": comp.get('emblem')
                }
            )
            
            home_team, _ = Team.objects.update_or_create(
                code=str(m['homeTeam']['id']),
                defaults={
                    "name": m['homeTeam']['name'],
                    "league": league,
                    "logo_url": m['homeTeam'].get('crest')
                }
            )
            
            away_team, _ = Team.objects.update_or_create(
                code=str(m['awayTeam']['id']),
                defaults={
                    "name": m['awayTeam']['name'],
                    "league": league,
                    "logo_url": m['awayTeam'].get('crest')
                }
            )
            
            match_date = datetime.fromisoformat(m['utcDate'].replace('Z', '+00:00'))
            
            match, _ = Match.objects.update_or_create(
                id=m['id'],
                defaults={
                    "league": league,
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_date": match_date,
                    "status": db_status,
                    "home_score": m.get('score', {}).get('fullTime', {}).get('home'),
                    "away_score": m.get('score', {}).get('fullTime', {}).get('away'),
                    "minute": "Live" if db_status == 'LIVE' else ('FT' if db_status == 'FINISHED' else None)
                }
            )
            CacheService.invalidate_match(match.id)

    def _generate_mock_fixtures(self, status):
        """Fills database with dynamic simulated fixture objects for demonstration."""
        now = timezone.now()
        
        # Pull existing teams
        leagues = League.objects.all()
        if not leagues.exists():
            self.sync_leagues_and_teams()
            leagues = League.objects.all()
            
        for league in leagues:
            teams = list(Team.objects.filter(league=league))
            if len(teams) < 2:
                continue
                
            # Create a couple matches per league
            for idx in range(2):
                home = teams[idx % len(teams)]
                away = teams[(idx + 1) % len(teams)]
                
                status_offset = 100000 if status == 'LIVE' else (200000 if status == 'FINISHED' else 300000)
                match_id = status_offset + league.id * 1000 + home.id * 10 + away.id
                
                if status == 'LIVE':
                    match_date = now - timedelta(minutes=random.randint(15, 75))
                    home_score = random.randint(0, 3)
                    away_score = random.randint(0, 2)
                    minute = f"{random.randint(20, 85)}'"
                elif status == 'FINISHED':
                    match_date = now - timedelta(hours=random.randint(2, 24))
                    home_score = random.choice([1, 2, 3, 0])
                    away_score = random.choice([1, 2, 0])
                    minute = 'FT'
                else: # SCHEDULED
                    match_date = now + timedelta(hours=random.randint(2, 48))
                    home_score = None
                    away_score = None
                    minute = None
                    
                match, _ = Match.objects.update_or_create(
                    id=match_id,
                    defaults={
                        "league": league,
                        "home_team": home,
                        "away_team": away,
                        "match_date": match_date,
                        "status": status,
                        "home_score": home_score,
                        "away_score": away_score,
                        "minute": minute
                    }
                )
                CacheService.invalidate_match(match.id)
