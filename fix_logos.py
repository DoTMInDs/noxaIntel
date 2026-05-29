"""
Fix team and league logo URLs.
Run with: python manage.py shell < fix_logos.py
Or:        python fix_logos.py
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from matches.models import League, Team

# --- Team Logos (using Wikipedia/official sources via direct CDN) ---
# Using media.api-sports.io which is the same CDN as the real API data
# These are the standard team IDs on API-Football / api-sports
team_logos = {
    # Premier League
    "ARS": "https://media.api-sports.io/football/teams/42.png",     # Arsenal
    "MCI": "https://media.api-sports.io/football/teams/50.png",     # Manchester City
    "LIV": "https://media.api-sports.io/football/teams/40.png",     # Liverpool
    "CHE": "https://media.api-sports.io/football/teams/49.png",     # Chelsea

    # La Liga
    "BAR": "https://media.api-sports.io/football/teams/529.png",    # Barcelona
    "RMA": "https://media.api-sports.io/football/teams/541.png",    # Real Madrid
    "ATM": "https://media.api-sports.io/football/teams/530.png",    # Atletico Madrid
    "SEV": "https://media.api-sports.io/football/teams/536.png",    # Sevilla

    # Bundesliga
    "BAY": "https://media.api-sports.io/football/teams/157.png",    # Bayern Munich
    "BVB": "https://media.api-sports.io/football/teams/165.png",    # Borussia Dortmund
    "RBL": "https://media.api-sports.io/football/teams/173.png",    # RB Leipzig
    "LEV": "https://media.api-sports.io/football/teams/168.png",    # Leverkusen

    # Serie A
    "INT": "https://media.api-sports.io/football/teams/505.png",    # Inter Milan
    "ACM": "https://media.api-sports.io/football/teams/489.png",    # AC Milan
    "JUV": "https://media.api-sports.io/football/teams/496.png",    # Juventus
    "NAP": "https://media.api-sports.io/football/teams/492.png",    # Napoli

    # Ligue 1
    "PSG": "https://media.api-sports.io/football/teams/85.png",     # PSG
    "MAR": "https://media.api-sports.io/football/teams/81.png",     # Marseille
    "LYO": "https://media.api-sports.io/football/teams/80.png",     # Lyon
    "MON": "https://media.api-sports.io/football/teams/91.png",     # Monaco
}

# --- League Logos ---
league_logos = {
    "PL": "https://media.api-sports.io/football/leagues/39.png",    # Premier League
    "LL": "https://media.api-sports.io/football/leagues/140.png",   # La Liga
    "BL": "https://media.api-sports.io/football/leagues/78.png",    # Bundesliga
    "SA": "https://media.api-sports.io/football/leagues/135.png",   # Serie A
    "L1": "https://media.api-sports.io/football/leagues/61.png",    # Ligue 1
}

updated_teams = 0
for code, logo_url in team_logos.items():
    count = Team.objects.filter(code=code).update(logo_url=logo_url)
    if count:
        updated_teams += count
        print(f"  [OK] Updated {code} logo")
    else:
        print(f"  [WARN] Team {code} not found")

print(f"\nUpdated {updated_teams} team logos")

updated_leagues = 0
for code, logo_url in league_logos.items():
    count = League.objects.filter(code=code).update(logo_url=logo_url)
    if count:
        updated_leagues += count
        print(f"  [OK] Updated {code} league logo")
    else:
        print(f"  [WARN] League {code} not found")

print(f"\nUpdated {updated_leagues} league logos")
print("\nLogo fix complete!")
