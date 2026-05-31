import logging
from decimal import Decimal

from django.utils import timezone
from django.db.models import Sum, Count, Q

from matches.models import Match
from betting.models import BettingTip, BetSlip, BetSelection
from predictions.models import Prediction
from services.prediction_service import PredictionService

logger = logging.getLogger('ai_engine')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wallet(user):
    """Safely return the user's Wallet instance (or None)."""
    try:
        return user.wallet
    except Exception:
        return None


def _profile(user):
    """Safely return the user's Profile instance (or None)."""
    return getattr(user, 'profile', None)


def _is_vip(user):
    prof = _profile(user)
    if not prof or not prof.subscription_tier:
        return False
    return prof.subscription_tier.name in ['Premium', 'VIP']


def _fmt_money(amount):
    return f"GHS {float(amount):,.2f}"


# ---------------------------------------------------------------------------
# Intent detection helpers
# ---------------------------------------------------------------------------

_PLACE_BET_KEYWORDS = [
    'place bet', 'place a bet', 'bet on', 'put a bet', 'wager', 'stake on',
    'i want to bet', 'place wager', 'put money on', 'bet for me'
]
_BALANCE_KEYWORDS = [
    'balance', 'wallet', 'how much', 'my money', 'funds', 'account balance',
    'how much do i have', 'check balance', 'my balance'
]
_ACTIVE_BETS_KEYWORDS = [
    'active bet', 'my bet', 'open bet', 'pending bet', 'running bet',
    'bet slip', 'show my bets', 'current bets', 'check my bets'
]
_BET_HISTORY_KEYWORDS = [
    'bet history', 'past bets', 'won bets', 'lost bets', 'settled bets',
    'previous bets', 'my history', 'won', 'lost', 'my wins', 'my losses'
]
_PREDICTION_KEYWORDS = [
    'predict', 'prediction', 'who will win', 'winning team', 'likely to win',
    'probable winner', 'odds', 'analyze', 'analysis', 'vs', 'versus'
]
_SAFE_BET_KEYWORDS = [
    'safe bet', 'safest', 'best bet', 'recommended bet', 'sure bet', 'banker'
]
_VIP_KEYWORDS = [
    'vip', 'premium', 'high confidence', 'confidence', 'top pick', 'top tips'
]
_LIVE_KEYWORDS = [
    'live', 'in play', 'current match', 'ongoing match', 'playing now',
    'live score', 'scores'
]
_UPCOMING_KEYWORDS = [
    'upcoming', 'next match', 'fixture', 'schedule', 'soon', 'today match',
    'tomorrow'
]
_DEPOSIT_KEYWORDS = [
    'deposit', 'top up', 'add money', 'fund wallet', 'add funds',
    'put money in', 'recharge'
]
_WITHDRAW_KEYWORDS = [
    'withdraw', 'cash out', 'take money', 'remove funds', 'send money',
    'payout', 'withdrawal'
]
_PROFILE_KEYWORDS = [
    'profile', 'my account', 'subscription', 'tier', 'plan', 'upgrade',
    'my plan', 'account details'
]
_HELP_KEYWORDS = [
    'help', 'what can you do', 'guide', 'how to', 'instructions', 'tutorial',
    'assist', 'commands', 'options'
]
_ACCA_KEYWORDS = [
    'acca', 'accumulator', 'combo', 'multiple', 'multis', 'parlay'
]


def _matches_any(query, keywords):
    return any(kw in query for kw in keywords)


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------

def _handle_place_bet(query, user):
    """Guide the user to place a bet via the prediction page."""
    wallet = _wallet(user)
    balance = wallet.balance if wallet else Decimal('0.00')

    # Try to extract a team from the query
    teams = TeamIdentifier.extract_teams_from_query(query)
    if teams:
        team1, team2 = teams[0], teams[1]
        match = (
            Match.objects.filter(
                home_team__name__icontains=team1,
                away_team__name__icontains=team2,
                status='SCHEDULED'
            ).select_related('home_team', 'away_team').first()
            or Match.objects.filter(
                home_team__name__icontains=team2,
                away_team__name__icontains=team1,
                status='SCHEDULED'
            ).select_related('home_team', 'away_team').first()
        )
        if match:
            prediction = getattr(match, 'prediction', None)
            if not prediction:
                try:
                    prediction = PredictionService.generate_prediction(match)
                except Exception:
                    prediction = None

            response = (
                f"🎯 Ready to bet on {match.home_team.name} vs {match.away_team.name}!\n\n"
                f"Your wallet balance: {_fmt_money(balance)}\n"
            )
            if prediction:
                response += (
                    f"AI suggests: {prediction.recommended_pick} "
                    f"(Confidence: {prediction.confidence_score}%)\n"
                )
            response += (
                "\nTo place your bet, open that match's prediction card and tap the bet button — "
                "you can choose your market (Home/Draw/Away or Over/Under) and enter your stake right there."
            )
            return response
        else:
            return (
                f"I couldn't find an upcoming fixture between those teams. "
                f"Browse the Predictions page to find a match and tap the bet button on the card. "
                f"Your current balance is {_fmt_money(balance)}."
            )
    else:
        return (
            f"Sure! To place a bet:\n"
            f"1️⃣  Go to **AI Predictions** in the menu.\n"
            f"2️⃣  Open any match card.\n"
            f"3️⃣  Choose your market (Home Win / Draw / Away Win / Over-Under).\n"
            f"4️⃣  Enter your stake and tap **Place Bet**.\n\n"
            f"Your current wallet balance is {_fmt_money(balance)}."
        )


def _handle_balance(query, user):
    wallet = _wallet(user)
    if not wallet:
        return "I can't find your wallet right now. Please log out and log back in."
    prof = _profile(user)
    tier_name = (prof.subscription_tier.name if prof and prof.subscription_tier else "Free")
    active_count = BetSlip.objects.filter(user=user, status='SUBMITTED').count()
    return (
        f"💰 Wallet Overview for {user.username}\n"
        f"• Balance: {_fmt_money(wallet.balance)}\n"
        f"• Subscription: {tier_name}\n"
        f"• Active bets: {active_count}\n\n"
        f"You can deposit via the Wallet → Deposit page, or withdraw anytime."
    )


def _handle_active_bets(query, user):
    slips = BetSlip.objects.filter(user=user, status='SUBMITTED').prefetch_related(
        'selections__match__home_team', 'selections__match__away_team'
    )
    if not slips.exists():
        return (
            "You have no active (pending) bets at the moment. "
            "Head to the Predictions page to place your first bet!"
        )
    total_stake = slips.aggregate(total=Sum('total_stake'))['total'] or 0
    total_potential = slips.aggregate(total=Sum('potential_payout'))['total'] or 0
    response = f"🎟️ You have {slips.count()} active bet slip(s):\n\n"
    for slip in slips[:5]:  # cap display at 5
        legs = slip.selections.all()
        leg_summary = ", ".join(
            f"{s.match.home_team.name} vs {s.match.away_team.name} ({s.get_market_display()})"
            for s in legs
        )
        response += (
            f"• Slip #{slip.pk} — Stake: {_fmt_money(slip.total_stake)} | "
            f"Potential: {_fmt_money(slip.potential_payout)}\n"
            f"  Legs: {leg_summary}\n"
        )
    response += (
        f"\nTotal staked: {_fmt_money(total_stake)} | "
        f"Total potential winnings: {_fmt_money(total_potential)}"
    )
    return response


def _handle_bet_history(query, user):
    won = BetSlip.objects.filter(user=user, status='WON').count()
    lost = BetSlip.objects.filter(user=user, status='LOST').count()
    total_won_amount = BetSlip.objects.filter(user=user, status='WON').aggregate(
        total=Sum('actual_payout')
    )['total'] or Decimal('0.00')
    total_lost_amount = BetSlip.objects.filter(user=user, status='LOST').aggregate(
        total=Sum('total_stake')
    )['total'] or Decimal('0.00')

    response = (
        f"📊 Your Betting History:\n"
        f"• Bets Won: {won} (Total winnings: {_fmt_money(total_won_amount)})\n"
        f"• Bets Lost: {lost} (Total staked: {_fmt_money(total_lost_amount)})\n"
    )
    if won + lost > 0:
        win_rate = round(won / (won + lost) * 100, 1)
        response += f"• Win Rate: {win_rate}%\n"
    response += "\nView your full history in the Bet Slips section of the app."
    return response


def _handle_prediction(query, user):
    teams = TeamIdentifier.extract_teams_from_query(query)
    if teams:
        team1, team2 = teams[0], teams[1]
        match = (
            Match.objects.filter(
                home_team__name__icontains=team1,
                away_team__name__icontains=team2
            ).select_related('home_team', 'away_team').first()
            or Match.objects.filter(
                home_team__name__icontains=team2,
                away_team__name__icontains=team1
            ).select_related('home_team', 'away_team').first()
        )
        if match:
            prediction = getattr(match, 'prediction', None)
            if not prediction:
                try:
                    prediction = PredictionService.generate_prediction(match)
                except Exception:
                    prediction = None

            if prediction:
                is_vip_content = prediction.is_vip_only and not _is_vip(user)
                response = (
                    f"🔮 AI Prediction: {match.home_team.name} vs {match.away_team.name}\n\n"
                    f"• Home Win: {prediction.home_win_prob}%\n"
                    f"• Draw: {prediction.draw_prob}%\n"
                    f"• Away Win: {prediction.away_win_prob}%\n"
                )
                if is_vip_content:
                    response += f"\n🔒 Full analysis is VIP-only. Upgrade your plan to unlock it."
                else:
                    response += (
                        f"\n• Recommended Pick: {prediction.recommended_pick}\n"
                        f"• Confidence: {prediction.confidence_score}%"
                    )
                return response
            else:
                return (
                    f"I found the fixture {match.home_team.name} vs {match.away_team.name} "
                    f"but the AI model hasn't generated a prediction for it yet. Check back soon!"
                )
        else:
            return (
                f"I couldn't find a fixture matching those teams in our database. "
                f"Try browsing the Predictions page where all upcoming matches are listed."
            )
    else:
        # No teams extracted — show top predictions
        preds = Prediction.objects.filter(
            confidence_score__gte=70
        ).select_related('match__home_team', 'match__away_team').order_by('-confidence_score')[:5]
        if not preds.exists():
            return "No strong predictions are ready right now. Check back in a few minutes!"
        response = "🔮 Top AI Predictions right now:\n\n"
        for p in preds:
            lock = "🔒 VIP" if (p.is_vip_only and not _is_vip(user)) else p.recommended_pick
            response += (
                f"• {p.match.home_team.name} vs {p.match.away_team.name}: "
                f"{lock} (Confidence: {p.confidence_score}%)\n"
            )
        return response


def _handle_safe_bets(query, user):
    tips = BettingTip.objects.filter(
        tip_type='SAFE'
    ).select_related('match__home_team', 'match__away_team').order_by('-confidence_score')[:5]
    if not tips.exists():
        return "No safe bets are in the system right now. The AI updates them periodically — check back soon!"
    response = "🟢 Safe Bets recommended by AI:\n\n"
    for tip in tips:
        response += (
            f"• {tip.match.home_team.name} vs {tip.match.away_team.name}: "
            f"{tip.description} (Odds: {tip.odds} | Confidence: {tip.confidence_score}%)\n"
        )
    return response


def _handle_vip_tips(query, user):
    if not _is_vip(user):
        prof = _profile(user)
        tier = prof.subscription_tier.name if prof and prof.subscription_tier else "Free"
        return (
            f"🔒 VIP Tips require a Premium or VIP subscription.\n"
            f"Your current plan is: **{tier}**.\n\n"
            f"Upgrade via Profile → Subscription to unlock:\n"
            f"• High-confidence VIP picks\n"
            f"• AI-driven accumulator suggestions\n"
            f"• Advanced match analysis"
        )
    preds = Prediction.objects.filter(
        confidence_score__gte=80
    ).select_related('match__home_team', 'match__away_team').order_by('-confidence_score')[:5]
    if not preds.exists():
        return "No VIP high-confidence predictions ready yet. Check back shortly!"
    response = "👑 VIP High-Confidence Picks:\n\n"
    for p in preds:
        response += (
            f"• {p.match.home_team.name} vs {p.match.away_team.name}: "
            f"{p.recommended_pick} (Confidence: {p.confidence_score}%)\n"
        )
    return response


def _handle_accas(query, user):
    tips = BettingTip.objects.filter(
        tip_type='ACCA'
    ).select_related('match__home_team', 'match__away_team').order_by('-confidence_score')[:4]
    if not tips.exists():
        return (
            "No accumulator tips are available right now. "
            "Try checking the VIP Accas tab on the Predictions page!"
        )
    # Build combined odds
    combined_odds = Decimal('1.00')
    response = "👑 AI Accumulator Builder:\n\n"
    for tip in tips:
        combined_odds *= tip.odds
        response += (
            f"• {tip.match.home_team.name} vs {tip.match.away_team.name}: "
            f"{tip.description} @ {tip.odds}\n"
        )
    response += f"\nCombined Odds: {round(combined_odds, 2)}"
    return response


def _handle_live(query, user):
    live = Match.objects.filter(status='LIVE').select_related('home_team', 'away_team')
    if not live.exists():
        return "⚽ No matches are live right now. Check back for kick-off times!"
    response = f"🔴 {live.count()} Live Match(es):\n\n"
    for m in live:
        score = (
            f"{m.home_score} - {m.away_score}"
            if m.home_score is not None
            else "0 - 0"
        )
        response += f"• {m.home_team.name} vs {m.away_team.name} — Score: {score} ({m.minute or 'Live'}′)\n"
    return response


def _handle_upcoming(query, user):
    upcoming = Match.objects.filter(
        status='SCHEDULED',
        kickoff_time__gte=timezone.now()
    ).select_related('home_team', 'away_team').order_by('kickoff_time')[:6]
    if not upcoming.exists():
        return "No upcoming matches found in our database at the moment."
    response = "📅 Upcoming Fixtures:\n\n"
    for m in upcoming:
        kick = m.kickoff_time.strftime('%d %b %H:%M') if m.kickoff_time else 'TBC'
        response += f"• {m.home_team.name} vs {m.away_team.name} — {kick}\n"
    return response


def _handle_deposit(query, user):
    wallet = _wallet(user)
    balance = wallet.balance if wallet else Decimal('0.00')
    return (
        f"💳 To deposit funds:\n"
        f"1️⃣  Go to **Wallet** in the side menu.\n"
        f"2️⃣  Tap **Deposit**.\n"
        f"3️⃣  Enter your Mobile Money number and amount.\n"
        f"4️⃣  A Paystack prompt will appear to confirm on your phone.\n\n"
        f"Your current balance is {_fmt_money(balance)}."
    )


def _handle_withdraw(query, user):
    wallet = _wallet(user)
    balance = wallet.balance if wallet else Decimal('0.00')
    return (
        f"🏧 To withdraw funds:\n"
        f"1️⃣  Go to **Wallet** in the side menu.\n"
        f"2️⃣  Tap **Withdraw**.\n"
        f"3️⃣  Enter your MoMo number, verify it, then enter the amount.\n"
        f"4️⃣  Tap **Withdraw** to confirm — funds arrive within minutes.\n\n"
        f"Your current withdrawable balance is {_fmt_money(balance)}."
    )


def _handle_profile(query, user):
    prof = _profile(user)
    wallet = _wallet(user)
    tier = prof.subscription_tier.name if prof and prof.subscription_tier else "Free"
    balance = wallet.balance if wallet else Decimal('0.00')
    total_bets = BetSlip.objects.filter(user=user).count()
    won_bets = BetSlip.objects.filter(user=user, status='WON').count()
    return (
        f"👤 Your Profile:\n"
        f"• Username: {user.username}\n"
        f"• Phone: {user.phone_number or 'Not set'}\n"
        f"• Email: {user.email or 'Not set'}\n"
        f"• Subscription: {tier}\n"
        f"• Wallet Balance: {_fmt_money(balance)}\n"
        f"• Total Bets: {total_bets} | Won: {won_bets}\n\n"
        f"Update your info via Profile → Edit Profile."
    )


def _handle_help(query, user):
    return (
        "🤖 NoxaIntel AI Assistant — Here's what I can do:\n\n"
        "📊 **Predictions & Analysis**\n"
        "• 'Predict Arsenal vs Chelsea'\n"
        "• 'Who will win Real Madrid vs Barcelona?'\n"
        "• 'Give me high confidence picks'\n\n"
        "🎯 **Betting**\n"
        "• 'Place a bet on Man City vs Liverpool'\n"
        "• 'Show my active bets'\n"
        "• 'Show my bet history'\n"
        "• 'Show safe bets'\n"
        "• 'Show accumulators'\n\n"
        "⚽ **Matches**\n"
        "• 'Show live matches'\n"
        "• 'What matches are upcoming today?'\n\n"
        "💰 **Wallet & Account**\n"
        "• 'What is my balance?'\n"
        "• 'How do I deposit?'\n"
        "• 'How do I withdraw?'\n"
        "• 'Show my profile'\n"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class VoiceService:
    """Full in-app AI copilot — maps any user speech/text query to an action or rich response."""

    @staticmethod
    def parse_voice_command(speech_text: str, user) -> str:
        query = speech_text.strip().lower()
        logger.info(f"[VoiceService] User={user.username} Query='{query}'")

        # --- Intent routing (order matters: more specific checks first) ---

        if _matches_any(query, _PLACE_BET_KEYWORDS):
            return _handle_place_bet(query, user)

        if _matches_any(query, _ACTIVE_BETS_KEYWORDS):
            return _handle_active_bets(query, user)

        if _matches_any(query, _BET_HISTORY_KEYWORDS) and 'place' not in query:
            return _handle_bet_history(query, user)

        if _matches_any(query, _BALANCE_KEYWORDS):
            return _handle_balance(query, user)

        if _matches_any(query, _SAFE_BET_KEYWORDS):
            return _handle_safe_bets(query, user)

        if _matches_any(query, _ACCA_KEYWORDS):
            return _handle_accas(query, user)

        if _matches_any(query, _VIP_KEYWORDS):
            return _handle_vip_tips(query, user)

        if _matches_any(query, _LIVE_KEYWORDS):
            return _handle_live(query, user)

        if _matches_any(query, _UPCOMING_KEYWORDS):
            return _handle_upcoming(query, user)

        if _matches_any(query, _DEPOSIT_KEYWORDS):
            return _handle_deposit(query, user)

        if _matches_any(query, _WITHDRAW_KEYWORDS):
            return _handle_withdraw(query, user)

        if _matches_any(query, _PROFILE_KEYWORDS):
            return _handle_profile(query, user)

        if _matches_any(query, _HELP_KEYWORDS):
            return _handle_help(query, user)

        if _matches_any(query, _PREDICTION_KEYWORDS):
            return _handle_prediction(query, user)

        # --- Fallback: try to see if it mentions teams ---
        teams = TeamIdentifier.extract_teams_from_query(query)
        if teams:
            return _handle_prediction(query, user)

        # --- Ultimate fallback ---
        return (
            "🤖 I'm not sure what you're asking. Try saying:\n"
            "• 'What is my balance?'\n"
            "• 'Show my active bets'\n"
            "• 'Predict Arsenal vs Chelsea'\n"
            "• 'Place a bet on Liverpool'\n"
            "• 'Show safe bets'\n"
            "• 'Help' — to see everything I can do."
        )


# ---------------------------------------------------------------------------
# Team name extractor (unchanged, but moved here for single-file clarity)
# ---------------------------------------------------------------------------

class TeamIdentifier:
    """Extracts team name mentions from a free-text query."""

    # Common team aliases — extend as needed
    _TEAM_ALIASES = {
        "city": "manchester city",
        "man city": "manchester city",
        "united": "manchester united",
        "man united": "manchester united",
        "madrid": "real madrid",
        "barca": "barcelona",
        "bvb": "dortmund",
        "juve": "juventus",
        "atletico": "atletico madrid",
        "spurs": "tottenham",
        "villa": "aston villa",
        "blues": "chelsea",
        "reds": "liverpool",
        "gunners": "arsenal",
        "gooners": "arsenal",
    }

    _TEAM_LIST = [
        "arsenal", "manchester city", "manchester united", "liverpool", "chelsea",
        "tottenham", "aston villa", "newcastle", "west ham", "brighton", "everton",
        "barcelona", "real madrid", "atletico madrid", "sevilla", "valencia",
        "bayern", "dortmund", "leipzig", "leverkusen", "wolfsburg",
        "inter", "milan", "juventus", "napoli", "roma", "lazio",
        "psg", "marseille", "lyon", "monaco", "lens",
        "ajax", "psv", "feyenoord",
        "porto", "benfica", "sporting",
        "celtic", "rangers",
    ]

    @classmethod
    def extract_teams_from_query(cls, query: str):
        """Return a list of (up to) two team name strings found in the query."""
        q = query.lower()

        # Apply aliases first
        for alias, canonical in cls._TEAM_ALIASES.items():
            if alias in q:
                q = q.replace(alias, canonical)

        found = []
        for team in cls._TEAM_LIST:
            if team in q and team not in found:
                found.append(team)
            if len(found) == 2:
                return found

        # If only one team found, try splitting by 'vs' / 'versus' / 'against'
        if len(found) == 1:
            for sep in (' vs ', ' versus ', ' against ', ' v '):
                if sep in q:
                    parts = q.split(sep, 1)
                    other = (parts[1] if found[0] in parts[0] else parts[0]).strip()
                    # Strip noise words
                    for noise in ['analyze ', 'predict ', 'show ', 'check ', 'who will win ', 'bet on ']:
                        other = other.replace(noise, '')
                    if other:
                        return [found[0], other.strip()]

        return found if len(found) >= 2 else None
