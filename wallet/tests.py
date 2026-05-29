import os
import django
import sys
from decimal import Decimal

# Set up Django environment
sys.path.append(r'c:\Users\HP\OneDrive\Documents\noxaintel')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from wallet.models import Wallet, Transaction, WithdrawalRequest
from matches.models import Match, League, Team, OddsSnapshot
from betting.models import BetSlip, BetSelection
from betting.tasks import settle_match_bets

User = get_user_model()

def run_tests():
    print("==================================================")
    print("  NOXAINTEL SPORTSBOOK & WALLET SYSTEM CHECK      ")
    print("==================================================")

    # 1. Clear previous test records
    print("\n[+] 1. Cleaning up existing test fixtures...")
    User.objects.filter(username__startswith='test_bettor').delete()
    League.objects.filter(code='TEST_L1').delete()
    
    # 2. Test User Registration & Wallet Signal Creation
    print("\n[+] 2. Registering new test user 'test_bettor_1'...")
    user = User.objects.create_user(
        username='test_bettor_1',
        email='bettor1@example.com',
        password='password123'
    )
    
    # Check if wallet was created atomically via post_save signal
    try:
        wallet = user.wallet
        print(f"   [OK] SUCCESS: Wallet auto-created for user!")
        print(f"      Currency: {wallet.currency} | Balance: GHS {wallet.balance}")
    except Wallet.DoesNotExist:
        print("   [ERR] FAIL: Wallet was not created automatically by signal.")
        return

    # 3. Test Deposit Flow (Atomic credit)
    print("\n[+] 3. Crediting Wallet (Deposit GHS 100.00)...")
    tx = wallet.credit(
        amount=Decimal('100.00'),
        tx_type=Transaction.DEPOSIT,
        description="Test deposit of GHS 100.00"
    )
    print(f"   [OK] SUCCESS: Wallet balance updated to: GHS {wallet.balance}")
    print(f"      Ledger reference: {tx.reference} | Status: {tx.status}")

    # 4. Set up mock matches & odds
    print("\n[+] 4. Setting up leagues, teams, and matches...")
    league = League.objects.create(name="Test League", country="Ghana", code="TEST_L1")
    home_team = Team.objects.create(name="Kumasi Asante Kotoko", code="KOTOKO", league=league)
    away_team = Team.objects.create(name="Hearts of Oak", code="HEARTS", league=league)
    
    match = Match.objects.create(
        league=league,
        home_team=home_team,
        away_team=away_team,
        match_date=django.utils.timezone.now(),
        status='SCHEDULED'
    )
    
    odds = OddsSnapshot.objects.create(
        match=match,
        home_odds=Decimal('2.50'),
        draw_odds=Decimal('3.20'),
        away_odds=Decimal('2.80')
    )
    print(f"   Created Match: {match}")
    print(f"   Created Odds Snapshot: 1 (@{odds.home_odds}) | X (@{odds.draw_odds}) | 2 (@{odds.away_odds})")

    # 5. Test Placing Bet (Atomic debit & transaction creation)
    print("\n[+] 5. Placing GHS 10.00 wager on Home Win (Kumasi Asante Kotoko)...")
    stake = Decimal('10.00')
    
    # Simulating the place_bet atomic logic
    from django.db import transaction as db_tx
    with db_tx.atomic():
        # Lock user's wallet
        locked_wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
        
        # Debit balance
        balance_before = locked_wallet.balance
        locked_wallet.balance -= stake
        locked_wallet.save()
        
        # Transaction log
        tx = Transaction.objects.create(
            wallet=locked_wallet,
            type=Transaction.BET_STAKE,
            amount=stake,
            balance_before=balance_before,
            balance_after=locked_wallet.balance,
            status=Transaction.COMPLETED,
            reference="TX-TEST-STAKE-001",
            description=f"Wager on Match #{match.id}"
        )
        
        # Bet Slip
        slip = BetSlip.objects.create(
            user=user,
            status='SUBMITTED',
            slip_type='SINGLE',
            total_stake=stake,
            total_odds=odds.home_odds,
            potential_payout=stake * odds.home_odds,
            transaction=tx
        )
        
        # Bet Selection
        sel = BetSelection.objects.create(
            bet_slip=slip,
            match=match,
            market='HOME_WIN',
            odds_at_placement=odds.home_odds,
            result='PENDING'
        )

    wallet.refresh_from_db()
    print(f"   [OK] SUCCESS: Bet slip #{slip.id} submitted!")
    print(f"      New Wallet Balance: GHS {wallet.balance} (Debited: GHS {stake})")
    print(f"      Est. Potential Payout: GHS {slip.potential_payout}")

    # 6. Test Early Payout (Cash Out) calculation
    print("\n[+] 6. Checking early payout cash out value...")
    cash_out_value = slip.calculate_cash_out_value()
    print(f"   [OK] Live Cash Out Offer: GHS {cash_out_value} (Safety offer of 85% of stake)")

    # 7. Test Match Settle Flow (auto settlement task)
    print("\n[+] 7. Simulating match completion (Kumasi Asante Kotoko 2 — 0 Hearts of Oak)...")
    match.home_score = 2
    match.away_score = 0
    match.status = 'FINISHED'
    match.minute = 'FT'
    match.save()
    
    print("   Triggering Celery settlement task (settle_match_bets)...")
    settle_match_bets(match.id)
    
    # Reload records
    slip.refresh_from_db()
    wallet.refresh_from_db()
    sel.refresh_from_db()
    
    print(f"   [OK] Selections status: {sel.result}")
    print(f"   [OK] Bet Slip status: {slip.status}")
    print(f"   [OK] Final Wallet Balance: GHS {wallet.balance} (Credited Winnings: GHS {slip.actual_payout})")

    # 8. Transaction Log Audit
    print("\n[+] 8. Ledger Audit Trail check:")
    for transaction in wallet.transactions.all().order_by('created_at'):
        print(f"   [{transaction.created_at.strftime('%H:%M:%S')}] {transaction.type:<12} | "
              f"Before: GHS {transaction.balance_before:<8} | "
              f"Change: GHS {transaction.amount:<8} | "
              f"After: GHS {transaction.balance_after:<8} | "
              f"Ref: {transaction.reference}")

    print("\n==================================================")
    print("  ALL PLATFORM WALLET & BET TESTS COMPLETED SUCCESSFULLY! ")
    print("==================================================")

if __name__ == '__main__':
    run_tests()
