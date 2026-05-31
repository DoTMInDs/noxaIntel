import json
import uuid
import logging
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.db import transaction as db_tx
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.contrib import messages

from .models import BettingTip, BetSlip, BetSelection
from matches.models import Match
from wallet.models import Wallet, Transaction
from analytics.utils import track_cache

logger = logging.getLogger(__name__)


def tips_dashboard(request):
    """Renders the betting recommendations dashboard."""
    return render(request, 'betting/dashboard.html')


def tips_filter_partial(request):
    """HTMX endpoint returning filtered betting tips with Redis caching."""
    tip_type = request.GET.get('type', 'all')
    is_vip = getattr(request.user, 'profile', None) and request.user.profile.subscription_tier.access_vip_tips

    cache_key = f"betting_tips_{tip_type}_vip_{is_vip}"
    cached_html = cache.get(cache_key)

    if cached_html:
        track_cache('tips_filter_partial', is_hit=True)
        return cached_html

    track_cache('tips_filter_partial', is_hit=False)

    tips = BettingTip.objects.select_related('match__home_team', 'match__away_team', 'match__league')

    if tip_type != 'all':
        tips = tips.filter(tip_type=tip_type.upper())

    # Keep VIP tips in the list so that we can render locked cards in the frontend, encouraging upgrades
    tips = tips[:30]

    response = render(request, 'betting/partials/tip_list.html', {'tips': tips, 'tip_type': tip_type})
    cache.set(cache_key, response, 60 * 5)
    return response


@login_required
def betslip_page(request):
    """Fallback standard page view of the betslip (mainly for mobile standalone redirect)."""
    return render(request, 'betting/betslip.html')


@login_required
def place_bet(request):
    """
    Atomically places a user bet slip from a JSON list of selections.
    Receives JSON payload containing:
    - selections: [{'match_id': int, 'market': str, 'odds': float}, ...]
    - stake: float
    - slip_type: 'SINGLE' | 'ACCUMULATOR'
    """
    if request.method != 'POST':
        return HttpResponseBadRequest("Only POST allowed.")

    try:
        data = json.loads(request.body.decode('utf-8'))
        selections_data = data.get('selections', [])
        stake = Decimal(str(data.get('stake', '0')))
        slip_type = data.get('slip_type', 'SINGLE').upper()
    except (ValueError, KeyError, TypeError) as e:
        return JsonResponse({'ok': False, 'message': 'Invalid payload data format.'}, status=400)

    # 1. Validation Checks
    if not selections_data:
        return JsonResponse({'ok': False, 'message': 'No selections provided in the betslip.'}, status=400)

    min_stake = getattr(settings, 'MIN_STAKE', Decimal('1.00'))
    max_stake = getattr(settings, 'MAX_STAKE', Decimal('10000.00'))
    max_payout = getattr(settings, 'MAX_PAYOUT', Decimal('100000.00'))

    if stake < min_stake:
        return JsonResponse({'ok': False, 'message': f'Minimum stake is GHS {min_stake:.2f}'}, status=400)
    if stake > max_stake:
        return JsonResponse({'ok': False, 'message': f'Maximum stake is GHS {max_stake:.2f}'}, status=400)

    # Calculate total odds and validate matches
    total_odds = Decimal('1.00')
    selections_to_create = []

    # Map request market keys to model keys
    market_map = {
        '1': 'HOME_WIN',
        'X': 'DRAW',
        '2': 'AWAY_WIN',
        'HOME_WIN': 'HOME_WIN',
        'DRAW': 'DRAW',
        'AWAY_WIN': 'AWAY_WIN',
        'O1.5': 'OVER_1_5',
        'OVER_1_5': 'OVER_1_5',
        'U1.5': 'UNDER_1_5',
        'UNDER_1_5': 'UNDER_1_5',
        'O2.5': 'OVER_2_5',
        'OVER_2_5': 'OVER_2_5',
        'U2.5': 'UNDER_2_5',
        'UNDER_2_5': 'UNDER_2_5',
        'O3.5': 'OVER_3_5',
        'OVER_3_5': 'OVER_3_5',
        'U3.5': 'UNDER_3_5',
        'UNDER_3_5': 'UNDER_3_5',
        'BTTS_YES': 'BTTS_YES',
        'BTTS_NO': 'BTTS_NO',
    }

    # Fetch and validate matches
    match_ids = [int(sel['match_id']) for sel in selections_data]
    matches = Match.objects.filter(id__in=match_ids).prefetch_related('odds_snapshots')
    match_dict = {m.id: m for m in matches}

    for sel in selections_data:
        match_id = int(sel['match_id'])
        req_market = sel['market']
        
        market = market_map.get(req_market)
        if not market:
            return JsonResponse({'ok': False, 'message': f'Invalid market type: {req_market}'}, status=400)

        match = match_dict.get(match_id)
        if not match:
            return JsonResponse({'ok': False, 'message': f'Match with ID {match_id} not found.'}, status=400)

        if match.status != 'SCHEDULED':
            return JsonResponse({'ok': False, 'message': f'Match {match} has already started or finished.'}, status=400)

        # Get active odds snapshot
        odds_snapshot = match.odds_snapshots.first()
        if not odds_snapshot:
            return JsonResponse({'ok': False, 'message': f'Odds are currently unavailable for {match}.'}, status=400)

        # Retrieve the odds value
        odds_val = Decimal('1.00')
        if market == 'HOME_WIN':
            odds_val = odds_snapshot.home_odds or Decimal('1.00')
        elif market == 'DRAW':
            odds_val = odds_snapshot.draw_odds or Decimal('1.00')
        elif market == 'AWAY_WIN':
            odds_val = odds_snapshot.away_odds or Decimal('1.00')
        elif market == 'OVER_1_5':
            # Scale from 2.5
            odds_val = Decimal(str(max(1.05, round(float(odds_snapshot.over_2_5_odds or 1.90) * 0.7, 2))))
        elif market == 'UNDER_1_5':
            # Scale from 2.5
            odds_val = Decimal(str(round(float(odds_snapshot.under_2_5_odds or 1.90) * 1.5, 2)))
        elif market == 'OVER_2_5':
            odds_val = odds_snapshot.over_2_5_odds or Decimal('1.00')
        elif market == 'UNDER_2_5':
            odds_val = odds_snapshot.under_2_5_odds or Decimal('1.00')
        elif market == 'OVER_3_5':
            # Scale from 2.5
            odds_val = Decimal(str(round(float(odds_snapshot.over_2_5_odds or 1.90) * 1.6, 2)))
        elif market == 'UNDER_3_5':
            # Scale from 2.5
            odds_val = Decimal(str(max(1.05, round(float(odds_snapshot.under_2_5_odds or 1.90) * 0.65, 2))))
        elif market == 'BTTS_YES':
            odds_val = odds_snapshot.btts_yes_odds or Decimal('1.00')
        elif market == 'BTTS_NO':
            odds_val = odds_snapshot.btts_no_odds or Decimal('1.00')

        total_odds *= odds_val
        selections_to_create.append({
            'match': match,
            'market': market,
            'odds_at_placement': odds_val
        })

    # Adjust slip type logic: If only 1 selection, force SINGLE
    if len(selections_to_create) == 1:
        slip_type = 'SINGLE'
        total_odds = selections_to_create[0]['odds_at_placement']
    else:
        # Multi odds is the product of all selections
        pass

    potential_payout = min(stake * total_odds, max_payout)

    # 2. Atomic Balance Lock & Bet Creation
    try:
        with db_tx.atomic():
            wallet = Wallet.objects.select_for_update().get(user=request.user)
            
            if wallet.balance < stake:
                return JsonResponse({'ok': False, 'message': f'Insufficient balance. Current: GHS {wallet.balance:.2f}'}, status=400)

            # Debit wallet balance
            balance_before = wallet.balance
            wallet.balance -= stake
            wallet.save(update_fields=['balance', 'updated_at'])

            # Create Transaction ledger
            tx_ref = f"NXB-{uuid.uuid4().hex[:12].upper()}"
            tx = Transaction.objects.create(
                wallet=wallet,
                type=Transaction.BET_STAKE,
                amount=stake,
                balance_before=balance_before,
                balance_after=wallet.balance,
                status=Transaction.COMPLETED,
                reference=tx_ref,
                description=f"Bet Slip Stake GHS {stake:.2f} ({slip_type})",
            )

            # Create BetSlip
            slip = BetSlip.objects.create(
                user=request.user,
                status='SUBMITTED',
                slip_type=slip_type,
                total_stake=stake,
                total_odds=total_odds,
                potential_payout=potential_payout,
                transaction=tx,
            )

            # Create Selections
            for s in selections_to_create:
                BetSelection.objects.create(
                    bet_slip=slip,
                    match=s['match'],
                    market=s['market'],
                    odds_at_placement=s['odds_at_placement'],
                    result='PENDING'
                )

        return JsonResponse({
            'ok': True,
            'message': 'Bet placed successfully!',
            'slip_id': slip.id,
            'new_balance': float(wallet.balance)
        })

    except Exception as e:
        logger.error(f"Error placing bet: {e}")
        return JsonResponse({'ok': False, 'message': 'An error occurred during bet placement. Please try again.'}, status=500)


@login_required
def my_bets(request):
    """Renders the betting history list with filter tabs for active vs settled bets."""
    slips = BetSlip.objects.filter(user=request.user).prefetch_related('selections__match__home_team', 'selections__match__away_team')
    
    # Calculate live cashout offers for active slips on the fly
    for slip in slips:
        if slip.status == 'SUBMITTED':
            slip.live_cashout_offer = slip.calculate_cash_out_value()
        else:
            slip.live_cashout_offer = 0.00

    context = {
        'slips': slips,
    }
    return render(request, 'betting/my_bets.html', context)


@login_required
def bet_detail(request, pk):
    """Displays a clean receipt view for a single user placed bet slip."""
    slip = get_object_or_404(BetSlip, pk=pk, user=request.user)
    selections = slip.selections.all().select_related('match__home_team', 'match__away_team', 'match__league')
    
    # Check if cashout is active
    live_cashout_offer = slip.calculate_cash_out_value() if slip.status == 'SUBMITTED' else 0.00

    context = {
        'slip': slip,
        'selections': selections,
        'live_cashout_offer': live_cashout_offer,
    }
    return render(request, 'betting/bet_detail.html', context)


@login_required
def cash_out(request, pk):
    """Atomically settles a bet slip early, crediting user with the cash-out value."""
    if request.method != 'POST':
        return HttpResponseBadRequest("Only POST allowed.")

    slip = get_object_or_404(BetSlip, pk=pk, user=request.user)
    
    if slip.status != 'SUBMITTED':
        messages.error(request, "This bet slip has already been settled.")
        return redirect('betting:my_bets')

    # Atomic Cash Out Settle
    try:
        with db_tx.atomic():
            # select_for_update user's wallet
            wallet = Wallet.objects.select_for_update().get(user=request.user)
            
            # Recalculate cash-out value securely within transaction lock
            cash_out_val = Decimal(str(slip.calculate_cash_out_value()))
            
            if cash_out_val <= 0:
                raise ValueError("Cash Out is currently unavailable for this bet.")

            # Settle slip early
            slip.status = 'CASHOUT'
            slip.is_cashed_out = True
            slip.cash_out_amount = cash_out_val
            slip.actual_payout = cash_out_val
            slip.settled_at = timezone.now()
            slip.save()

            # Credit wallet
            balance_before = wallet.balance
            wallet.balance += cash_out_val
            wallet.save(update_fields=['balance', 'updated_at'])

            # Create Transaction ledger
            Transaction.objects.create(
                wallet=wallet,
                type=Transaction.CASHOUT,
                amount=cash_out_val,
                balance_before=balance_before,
                balance_after=wallet.balance,
                status=Transaction.COMPLETED,
                reference=f"NXC-{uuid.uuid4().hex[:12].upper()}",
                description=f"Early Cash Out Payout on Bet #{slip.id}",
                meta={'bet_slip_id': slip.id, 'original_stake': float(slip.total_stake)}
            )

        messages.success(request, f"Successfully Cashed Out Bet #{slip.id} for GHS {cash_out_val:.2f}!")
    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.error(f"Error cashing out: {e}")
        messages.error(request, "Failed to complete early payout cash out.")

    return redirect('betting:my_bets')
