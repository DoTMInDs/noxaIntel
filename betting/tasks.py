import logging
import uuid
from decimal import Decimal

from celery import shared_task
from django.db import transaction as db_tx
from django.utils import timezone
from django.conf import settings

from .models import BetSlip, BetSelection
from matches.models import Match
from wallet.models import Wallet, Transaction
from notifications.push_service import notify_user

logger = logging.getLogger(__name__)


@shared_task
def settle_match_bets(match_id):
    """
    Settles all selections and bet slips related to a finished match.
    Called automatically when a match transitions to the 'FINISHED' status.
    """
    logger.info(f"Settle Match Bets starting for Match ID: {match_id}")
    try:
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        logger.error(f"Match with ID {match_id} does not exist.")
        return

    if match.status != 'FINISHED':
        logger.warning(f"Match {match} is not in FINISHED status. Skipping settlement.")
        return

    home_score = match.home_score if match.home_score is not None else 0
    away_score = match.away_score if match.away_score is not None else 0
    total_goals = home_score + away_score

    # Determine outcomes
    outcomes = {
        'HOME_WIN': home_score > away_score,
        'DRAW': home_score == away_score,
        'AWAY_WIN': home_score < away_score,
        'OVER_2_5': total_goals > 2,
        'UNDER_2_5': total_goals < 3,
        'BTTS_YES': home_score > 0 and away_score > 0,
        'BTTS_NO': home_score == 0 or away_score == 0,
    }

    # Query all pending selections on this match
    selections = BetSelection.objects.filter(match=match, result='PENDING')
    
    # Track the slips that need updating
    slip_ids_to_check = set()

    for sel in selections:
        market = sel.market
        is_won = outcomes.get(market, False)
        
        sel.result = 'WON' if is_won else 'LOST'
        sel.save(update_fields=['result'])
        slip_ids_to_check.add(sel.bet_slip_id)
        logger.info(f"Selection ID {sel.id} on Match {match} marked as {sel.result}")

    # Resolve affected slips
    for slip_id in slip_ids_to_check:
        settle_betslip(slip_id)


def settle_betslip(slip_id):
    """
    Secure, atomic evaluation and settlement of a single BetSlip.
    If all selections win, credits user's wallet with payout and logs transaction.
    """
    try:
        with db_tx.atomic():
            # Lock the slip to prevent duplicate processing
            slip = BetSlip.objects.select_for_update().get(id=slip_id)
            if slip.status != 'SUBMITTED':
                # Already settled or cashed out
                return

            selections = list(slip.selections.all())
            total_legs = len(selections)
            won_legs = sum(1 for s in selections if s.result == 'WON')
            lost_legs = sum(1 for s in selections if s.result == 'LOST')
            pending_legs = sum(1 for s in selections if s.result == 'PENDING')
            void_legs = sum(1 for s in selections if s.result == 'VOID')

            if pending_legs > 0:
                # Still waiting for other matches to finish
                return

            # All legs resolved!
            if lost_legs > 0:
                # Slip is LOST
                slip.status = 'LOST'
                slip.settled_at = timezone.now()
                slip.save(update_fields=['status', 'settled_at'])
                
                # Notify User of loss
                try:
                    notify_user(
                        user=slip.user,
                        title="Bet Settled: Lost ❌",
                        body=f"Your Bet #{slip.id} ({slip.slip_type}) of GHS {slip.total_stake:.2f} has been settled as Lost.",
                        notification_type='PREDICTION',
                        url='/bet/my-bets/'
                    )
                except Exception as e:
                    logger.error(f"Failed to send loss notification to {slip.user.username}: {e}")
                logger.info(f"Bet Slip #{slip.id} settled as LOST.")

            elif won_legs + void_legs == total_legs:
                # Slip is WON!
                # If there are void legs, recalculate the odds dynamically
                final_odds = Decimal('1.00')
                for s in selections:
                    if s.result == 'WON':
                        final_odds *= s.odds_at_placement
                
                payout = slip.total_stake * final_odds
                max_payout = getattr(settings, 'MAX_PAYOUT', Decimal('100000.00'))
                payout = min(payout, max_payout)

                slip.status = 'WON'
                slip.actual_payout = payout
                slip.settled_at = timezone.now()
                slip.save(update_fields=['status', 'actual_payout', 'settled_at'])

                # Credit user wallet atomically
                wallet = Wallet.objects.select_for_update().get(user=slip.user)
                balance_before = wallet.balance
                wallet.balance += payout
                wallet.save(update_fields=['balance', 'updated_at'])

                # Create BET_WIN Transaction
                tx_ref = f"NXW-{uuid.uuid4().hex[:12].upper()}"
                tx = Transaction.objects.create(
                    wallet=wallet,
                    type=Transaction.BET_WIN,
                    amount=payout,
                    balance_before=balance_before,
                    balance_after=wallet.balance,
                    status=Transaction.COMPLETED,
                    reference=tx_ref,
                    description=f"Winnings for Bet #{slip.id}",
                    meta={'bet_slip_id': slip.id, 'odds': float(final_odds)}
                )

                # Set transaction relation on the slip
                slip.transaction = tx
                slip.save(update_fields=['transaction'])

                # Notify User of win
                try:
                    notify_user(
                        user=slip.user,
                        title="Bet Settled: WON! 🎉",
                        body=f"Congratulations! Your Bet #{slip.id} ({slip.slip_type}) won! GHS {payout:.2f} credited to your wallet.",
                        notification_type='PREDICTION',
                        url='/bet/my-bets/'
                    )
                except Exception as e:
                    logger.error(f"Failed to send win notification to {slip.user.username}: {e}")
                logger.info(f"Bet Slip #{slip.id} settled as WON. Payout GHS {payout:.2f} credited.")
    except Exception as e:
        logger.error(f"Error settling Bet Slip #{slip_id}: {e}")
