"""
Seed script - run with: python manage.py shell < seed_data.py
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import random

from users.models import SubscriptionTier
from matches.models import League, Team, Match, OddsSnapshot
from predictions.models import Prediction, AIAnalysis
from betting.models import BettingTip
from analytics.models import ModelAccuracyReport, CacheMetrics

print("🌱 Seeding database...")

# --- Subscription Tiers ---
tiers_data = [
    {"name": "Free", "price": 0, "description": "Basic match dashboard and standard predictions.", "access_advanced_ai": False, "access_vip_tips": False, "access_ai_assistant": False},
    {"name": "Premium", "price": 9.99, "description": "Advanced AI predictions, deeper statistical analysis, and priority alerts.", "access_advanced_ai": True, "access_vip_tips": False, "access_ai_assistant": False},
    {"name": "VIP", "price": 24.99, "description": "Full access: VIP betting tips, AI Chat Assistant, and all premium features.", "access_advanced_ai": True, "access_vip_tips": True, "access_ai_assistant": True},
]
for t in tiers_data:
    SubscriptionTier.objects.update_or_create(name=t["name"], defaults=t)
print("  ✅ Subscription tiers created")

# --- Leagues ---
leagues_data = [
    {"name": "Premier League", "country": "England", "code": "PL", "logo_url": "https://media.api-sports.io/football/leagues/39.png"},
    {"name": "La Liga", "country": "Spain", "code": "LL", "logo_url": "https://media.api-sports.io/football/leagues/140.png"},
    {"name": "Bundesliga", "country": "Germany", "code": "BL", "logo_url": "https://media.api-sports.io/football/leagues/78.png"},
    {"name": "Serie A", "country": "Italy", "code": "SA", "logo_url": "https://media.api-sports.io/football/leagues/135.png"},
    {"name": "Ligue 1", "country": "France", "code": "L1", "logo_url": "https://media.api-sports.io/football/leagues/61.png"},
]
leagues = {}
for l in leagues_data:
    obj, _ = League.objects.update_or_create(code=l["code"], defaults=l)
    leagues[l["code"]] = obj
print("  ✅ Leagues created")

# --- Teams ---
# (name, code, logo_url)
teams_data = {
    "PL": [
        ("Arsenal", "ARS", "https://media.api-sports.io/football/teams/42.png"),
        ("Manchester City", "MCI", "https://media.api-sports.io/football/teams/50.png"),
        ("Liverpool", "LIV", "https://media.api-sports.io/football/teams/40.png"),
        ("Chelsea", "CHE", "https://media.api-sports.io/football/teams/49.png"),
    ],
    "LL": [
        ("Barcelona", "BAR", "https://media.api-sports.io/football/teams/529.png"),
        ("Real Madrid", "RMA", "https://media.api-sports.io/football/teams/541.png"),
        ("Atletico Madrid", "ATM", "https://media.api-sports.io/football/teams/530.png"),
        ("Sevilla", "SEV", "https://media.api-sports.io/football/teams/536.png"),
    ],
    "BL": [
        ("Bayern Munich", "BAY", "https://media.api-sports.io/football/teams/157.png"),
        ("Borussia Dortmund", "BVB", "https://media.api-sports.io/football/teams/165.png"),
        ("RB Leipzig", "RBL", "https://media.api-sports.io/football/teams/173.png"),
        ("Leverkusen", "LEV", "https://media.api-sports.io/football/teams/168.png"),
    ],
    "SA": [
        ("Inter Milan", "INT", "https://media.api-sports.io/football/teams/505.png"),
        ("AC Milan", "ACM", "https://media.api-sports.io/football/teams/489.png"),
        ("Juventus", "JUV", "https://media.api-sports.io/football/teams/496.png"),
        ("Napoli", "NAP", "https://media.api-sports.io/football/teams/492.png"),
    ],
    "L1": [
        ("PSG", "PSG", "https://media.api-sports.io/football/teams/85.png"),
        ("Marseille", "MAR", "https://media.api-sports.io/football/teams/81.png"),
        ("Lyon", "LYO", "https://media.api-sports.io/football/teams/80.png"),
        ("Monaco", "MON", "https://media.api-sports.io/football/teams/91.png"),
    ],
}
teams = {}
for league_code, team_list in teams_data.items():
    for name, code, logo_url in team_list:
        obj, _ = Team.objects.update_or_create(code=code, defaults={"name": name, "league": leagues[league_code], "logo_url": logo_url})
        teams[code] = obj
print("  ✅ Teams created")

# --- Matches ---
now = timezone.now()
statuses = ["SCHEDULED", "LIVE", "FINISHED"]
matches = []
match_pairs = [
    ("ARS", "MCI", "PL"), ("LIV", "CHE", "PL"),
    ("BAR", "RMA", "LL"), ("ATM", "SEV", "LL"),
    ("BAY", "BVB", "BL"), ("RBL", "LEV", "BL"),
    ("INT", "ACM", "SA"), ("JUV", "NAP", "SA"),
    ("PSG", "MAR", "L1"), ("LYO", "MON", "L1"),
]

for i, (home, away, league) in enumerate(match_pairs):
    status = statuses[i % 3]
    if status == "FINISHED":
        match_date = now - timedelta(hours=random.randint(2, 48))
        home_score = random.randint(0, 4)
        away_score = random.randint(0, 3)
    elif status == "LIVE":
        match_date = now - timedelta(minutes=random.randint(10, 80))
        home_score = random.randint(0, 2)
        away_score = random.randint(0, 2)
    else: # SCHEDULED
        match_date = now + timedelta(hours=random.randint(1, 72))
        home_score = 0
        away_score = 0

    match, _ = Match.objects.update_or_create(
        home_team=teams[home], away_team=teams[away], league=leagues[league],
        defaults={
            "match_date": match_date,
            "status": status,
            "home_score": home_score,
            "away_score": away_score,
            "minute": random.randint(45, 90) if status == "LIVE" else None,
        }
    )
    matches.append(match)

    # Odds snapshot
    OddsSnapshot.objects.update_or_create(
        match=match,
        defaults={
            "home_odds": Decimal(str(round(random.uniform(1.3, 4.0), 2))),
            "draw_odds": Decimal(str(round(random.uniform(2.5, 4.5), 2))),
            "away_odds": Decimal(str(round(random.uniform(1.5, 5.0), 2))),
            "over_2_5_odds": Decimal(str(round(random.uniform(1.6, 2.5), 2))),
            "under_2_5_odds": Decimal(str(round(random.uniform(1.4, 2.3), 2))),
            "btts_yes_odds": Decimal(str(round(random.uniform(1.5, 2.2), 2))),
            "btts_no_odds": Decimal(str(round(random.uniform(1.5, 2.5), 2))),
        }
    )
print("  ✅ Matches and odds created")

# --- Predictions ---
picks = ["Home Win", "Draw", "Away Win", "Over 2.5", "BTTS Yes"]
for match in matches:
    Prediction.objects.update_or_create(
        match=match,
        defaults={
            "home_win_prob": round(random.uniform(20, 60), 1),
            "draw_prob": round(random.uniform(15, 35), 1),
            "away_win_prob": round(random.uniform(15, 55), 1),
            "over_2_5_prob": round(random.uniform(30, 70), 1),
            "under_2_5_prob": round(random.uniform(30, 70), 1),
            "btts_yes_prob": round(random.uniform(30, 65), 1),
            "btts_no_prob": round(random.uniform(35, 70), 1),
            "confidence_score": round(random.uniform(55, 95), 1),
            "recommended_pick": random.choice(picks),
            "is_vip_only": random.random() > 0.7,
        }
    )

    AIAnalysis.objects.update_or_create(
        match=match,
        defaults={
            "tactical_breakdown": f"The {match.home_team.name} typically employs a high-pressing 4-3-3 formation against {match.away_team.name}'s defensive 5-4-1 setup. Key tactical battle will be in the midfield zones.",
            "key_player_matchups": f"Watch for the duel between {match.home_team.name}'s attacking midfielder and {match.away_team.name}'s defensive midfielder. Set-piece deliveries will be crucial.",
            "weather_impact": "Mild conditions expected. Temperature around 18°C with light wind — minimal impact on match dynamics.",
            "final_verdict": f"Our AI models give a slight edge to {match.home_team.name} based on recent form, but the tight odds suggest this will be a competitive fixture. Consider value in the Over 2.5 market.",
        }
    )
print("  ✅ Predictions and AI analysis created")

# --- Betting Tips ---
tip_types = ["safe", "value", "acca"]
for match in matches:
    for tip_type in random.sample(tip_types, k=random.randint(1, 2)):
        BettingTip.objects.update_or_create(
            match=match, tip_type=tip_type,
            defaults={
                "odds": Decimal(str(round(random.uniform(1.3, 8.0), 2))),
                "confidence_score": round(random.uniform(50, 95), 1),
                "description": f"{'Safe pick' if tip_type == 'safe' else 'Value opportunity' if tip_type == 'value' else 'Accumulator leg'}: {match.home_team.name} vs {match.away_team.name}. {random.choice(['Back the home side.', 'Consider the draw.', 'Over 2.5 goals expected.', 'BTTS looks solid.'])}",
                "is_vip_only": tip_type == "acca" or random.random() > 0.6,
            }
        )
print("  ✅ Betting tips created")

# --- Analytics Records ---
model_names = ["XGBoost-v3", "NeuralNet-v2", "Ensemble-Pro"]
for i, name in enumerate(model_names):
    for j in range(5):
        total = random.randint(80, 200)
        correct = int(total * random.uniform(0.55, 0.78))
        ModelAccuracyReport.objects.create(
            model_name=name,
            total_predictions=total,
            correct_predictions=correct,
            accuracy_percentage=round(correct / total * 100, 2),
            roi_percentage=round(random.uniform(3, 18), 2),
            recorded_at=now - timedelta(days=j * 7),
        )

for endpoint in ["predictions_detail", "betting_tips_filter"]:
    hits = random.randint(500, 2000)
    misses = random.randint(50, 300)
    CacheMetrics.objects.create(
        endpoint_name=endpoint,
        cache_hits=hits,
        cache_misses=misses,
        hit_ratio=round(hits / (hits + misses) * 100, 2),
    )
print("  ✅ Analytics records created")

print("\n🎉 Seed complete! All demo data populated.")
