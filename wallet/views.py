import json
import logging
import uuid
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.contrib import messages
from django.db import transaction as db_tx
from django.utils import timezone
from django.conf import settings

from .models import Wallet, Transaction, WithdrawalRequest
from . import paystack

logger = logging.getLogger(__name__)


@login_required
def overview(request):
    """Renders the main wallet page with balance, action grid, and transactions."""
    wallet, created = Wallet.objects.get_or_create(user=request.user, currency='GHS')
    
    # Simple pagination or top 20 recent transactions
    transactions = wallet.transactions.all().order_by('-created_at')[:20]
    
    context = {
        'wallet': wallet,
        'transactions': transactions,
    }
    return render(request, 'wallet/overview.html', context)


@login_required
def deposit_initiate(request):
    """Initiates a Paystack deposit transaction and redirects to checkout."""
    if request.method == 'POST':
        amount_str = request.POST.get('amount', '0')
        try:
            amount = Decimal(amount_str)
        except (ValueError, TypeError):
            messages.error(request, "Invalid deposit amount entered.")
            return redirect('wallet:overview')

        min_deposit = getattr(settings, 'MIN_DEPOSIT', Decimal('3.00'))
        if amount < min_deposit:
            messages.error(request, f"Minimum deposit is GHS {min_deposit:.2f}")
            return redirect('wallet:overview')

        wallet, _ = Wallet.objects.get_or_create(user=request.user, currency='GHS')
        reference = f"NXD-{uuid.uuid4().hex[:12].upper()}"

        # Initialize transaction with Paystack
        callback_url = request.build_absolute_uri('/wallet/deposit/verify/')
        
        # In a real setup, if keys are mock placeholders we simulate immediate success for testing
        if settings.PAYSTACK_SECRET_KEY.startswith('sk_test_mock'):
            # Simulated sandbox mode
            with db_tx.atomic():
                tx = Transaction.objects.create(
                    wallet=wallet,
                    type=Transaction.DEPOSIT,
                    amount=amount,
                    balance_before=wallet.balance,
                    balance_after=wallet.balance,
                    status=Transaction.PENDING,
                    reference=reference,
                    description=f"Simulated deposit of GHS {amount:.2f}",
                )
            
            messages.info(request, "[DEMO MODE] Loading Simulated Paystack Gateway...")
            return redirect('wallet:deposit_simulate', reference=reference)

        res = paystack.initialize_transaction(amount, request.user.email, reference, callback_url)
        if res.get('ok'):
            # Create a pending deposit Transaction
            Transaction.objects.create(
                wallet=wallet,
                type=Transaction.DEPOSIT,
                amount=amount,
                balance_before=wallet.balance,
                balance_after=wallet.balance,
                status=Transaction.PENDING,
                reference=reference,
                description=f"Deposit of GHS {amount:.2f} via Paystack",
            )
            return redirect(res['authorization_url'])
        else:
            messages.error(request, f"Could not initiate payment: {res.get('message')}")
            return redirect('wallet:overview')

    return render(request, 'wallet/deposit.html')


@login_required
def deposit_verify(request):
    """Callback landing page verifying Paystack transaction status."""
    reference = request.GET.get('reference')
    if not reference:
        messages.error(request, "No transaction reference provided.")
        return redirect('wallet:overview')

    # Fetch corresponding Transaction
    tx = get_object_or_404(Transaction, reference=reference, type=Transaction.DEPOSIT)
    
    if tx.status == Transaction.COMPLETED:
        messages.success(request, f"Deposit of GHS {tx.amount:.2f} completed successfully!")
        return redirect('wallet:overview')

    # Simulation fallback for demo
    if settings.PAYSTACK_SECRET_KEY.startswith('sk_test_mock'):
        with db_tx.atomic():
            wallet = Wallet.objects.select_for_update().get(pk=tx.wallet.pk)
            if tx.status == Transaction.PENDING:
                balance_before = wallet.balance
                wallet.balance += tx.amount
                wallet.save(update_fields=['balance', 'updated_at'])
                tx.balance_before = balance_before
                tx.balance_after = wallet.balance
                tx.status = Transaction.COMPLETED
                tx.save()
        messages.success(request, f"[DEMO] Simulated deposit of GHS {tx.amount:.2f} successful!")
        return redirect('wallet:overview')

    # Call Paystack to verify
    res = paystack.verify_transaction(reference)
    if res.get('ok'):
        with db_tx.atomic():
            wallet = Wallet.objects.select_for_update().get(pk=tx.wallet.pk)
            # Recheck status to prevent race conditions
            tx = Transaction.objects.select_for_update().get(pk=tx.pk)
            if tx.status == Transaction.PENDING:
                balance_before = wallet.balance
                wallet.balance += res['amount_ghs']
                wallet.save(update_fields=['balance', 'updated_at'])
                
                tx.balance_before = balance_before
                tx.balance_after = wallet.balance
                tx.status = Transaction.COMPLETED
                tx.meta = res.get('raw', {})
                tx.save()
        
        messages.success(request, f"Deposit of GHS {res['amount_ghs']:.2f} successful!")
    else:
        with db_tx.atomic():
            tx.status = Transaction.FAILED
            tx.save()
        messages.error(request, f"Deposit verification failed: {res.get('message')}")

    return redirect('wallet:overview')


@login_required
def withdraw_request(request):
    """Handles bank and mobile money withdrawal form submissions."""
    wallet, _ = Wallet.objects.get_or_create(user=request.user, currency='GHS')

    if request.method == 'POST':
        amount_str = request.POST.get('amount', '0')
        payout_type = request.POST.get('payout_type', WithdrawalRequest.BANK)
        
        if payout_type == WithdrawalRequest.MOBILE_MONEY:
            bank_code = request.POST.get('momo_code')
            account_number = request.POST.get('momo_account_number')
            momo_names = {'MTN': 'MTN Mobile Money', 'VDF': 'Telecel Cash', 'ATL': 'AT Money'}
            bank_name = momo_names.get(bank_code, request.POST.get('momo_bank_name', 'Mobile Money'))
        else:
            payout_type = WithdrawalRequest.BANK
            bank_code = request.POST.get('bank_code')
            account_number = request.POST.get('bank_account_number')
            bank_name = request.POST.get('bank_name', 'Unknown Bank')

        account_name = request.POST.get('account_name', '').strip()

        try:
            amount = Decimal(amount_str)
        except (ValueError, TypeError):
            messages.error(request, "Invalid withdrawal amount entered.")
            return redirect('wallet:overview')

        min_withdraw = getattr(settings, 'MIN_WITHDRAWAL', Decimal('3.00'))
        if amount < min_withdraw:
            messages.error(request, f"Minimum withdrawal is GHS {min_withdraw:.2f}")
            return redirect('wallet:overview')

        if not bank_code or not account_number or not account_name:
            messages.error(request, "Please fill in all banking/mobile money details.")
            return redirect('wallet:overview')

        # Atomic checks and balance updates
        try:
            with db_tx.atomic():
                # select_for_update prevents concurrent debiting
                locked_wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
                
                if locked_wallet.is_locked:
                    raise ValueError("Withdrawals are currently locked on this wallet. Contact Support.")

                if locked_wallet.balance < amount:
                    raise ValueError(f"Insufficient funds. Balance: GHS {locked_wallet.balance:.2f}")

                # 1. Create a pending withdrawal transaction (which acts as a debit)
                balance_before = locked_wallet.balance
                locked_wallet.balance -= amount
                locked_wallet.save(update_fields=['balance', 'updated_at'])

                tx_reference = f"NXW-{uuid.uuid4().hex[:12].upper()}"
                tx = Transaction.objects.create(
                    wallet=locked_wallet,
                    type=Transaction.WITHDRAWAL,
                    amount=amount,
                    balance_before=balance_before,
                    balance_after=locked_wallet.balance,
                    status=Transaction.PENDING,
                    reference=tx_reference,
                    description=f"Withdrawal GHS {amount:.2f} to {bank_name} ({account_number})",
                )

                # 2. Create WithdrawalRequest
                wr = WithdrawalRequest.objects.create(
                    wallet=locked_wallet,
                    amount=amount,
                    payout_type=payout_type,
                    bank_name=bank_name,
                    bank_code=bank_code,
                    account_number=account_number,
                    account_name=account_name,
                    status=WithdrawalRequest.PENDING,
                    transaction=tx,
                )

            # In sandbox / demo mode: redirect to interactive live payout settlement tracker!
            if settings.PAYSTACK_SECRET_KEY.startswith('sk_test_mock'):
                messages.info(request, "[DEMO] Redirecting to Real-Time Settlement Tracker...")
                return redirect('wallet:withdraw_simulate', pk=wr.id)

            # Outside demo: call celery worker or proceed immediately
            rec_res = paystack.create_transfer_recipient(bank_code, account_number, account_name)
            if rec_res.get('ok'):
                recipient_code = rec_res['recipient_code']
                wr.paystack_recipient_code = recipient_code
                wr.save()

                tf_res = paystack.initiate_transfer(amount, recipient_code, f"NoxaIntel Payout #{wr.id}", tx_reference)
                if tf_res.get('ok'):
                    with db_tx.atomic():
                        wr.status = WithdrawalRequest.PROCESSING
                        wr.transfer_code = tf_res['transfer_code']
                        wr.save()
                    messages.success(request, "Withdrawal request initiated successfully. Processing payment...")
                else:
                    # Rollback the transaction atomically by refunding
                    with db_tx.atomic():
                        locked_wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
                        locked_wallet.balance += amount
                        locked_wallet.save(update_fields=['balance'])
                        
                        tx.status = Transaction.FAILED
                        tx.description += " - Failed at Paystack Transfer Initiation"
                        tx.save()
                        
                        wr.status = WithdrawalRequest.FAILED
                        wr.failure_reason = tf_res.get('message', 'Failed to initiate Paystack transfer.')
                        wr.save()
                    messages.error(request, f"Failed to process payout: {tf_res.get('message')}")
            else:
                # Rollback
                with db_tx.atomic():
                    locked_wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
                    locked_wallet.balance += amount
                    locked_wallet.save(update_fields=['balance'])
                    
                    tx.status = Transaction.FAILED
                    tx.save()
                    
                    wr.status = WithdrawalRequest.FAILED
                    wr.failure_reason = rec_res.get('message', 'Failed to create transfer recipient.')
                    wr.save()
                messages.error(request, f"Failed to verify bank recipient details: {rec_res.get('message')}")

        except ValueError as e:
            messages.error(request, str(e))

        return redirect('wallet:overview')
    
    context = {
        "wallet": wallet,
    }

    return render(request, 'wallet/withdraw.html', context)


@csrf_exempt
def paystack_webhook(request):
    """CSRF-exempt handler for Paystack webhooks supporting both charge & transfer events."""
    if request.method != 'POST':
        return HttpResponseBadRequest("Invalid request method.")

    signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE')
    if not signature:
        return HttpResponseBadRequest("No webhook signature supplied.")

    payload_bytes = request.body
    # Verify signature
    # (Skip verification in demo mode with mock keys to allow easier local tests if needed)
    if not settings.PAYSTACK_SECRET_KEY.startswith('sk_test_mock'):
        if not paystack.verify_webhook_signature(payload_bytes, signature):
            logger.warning("Paystack webhook signature verification failed.")
            return HttpResponseBadRequest("Invalid signature.")

    try:
        event_data = json.loads(payload_bytes.decode('utf-8'))
    except ValueError:
        return HttpResponseBadRequest("Malformed JSON.")

    event_type = event_data.get('event')
    data = event_data.get('data', {})
    reference = data.get('reference')

    logger.info(f"Received Paystack webhook event: {event_type} (Reference: {reference})")

    if event_type == 'charge.success':
        # Re-verify and credit user wallet securely
        tx = Transaction.objects.filter(reference=reference, type=Transaction.DEPOSIT).first()
        if tx and tx.status == Transaction.PENDING:
            with db_tx.atomic():
                wallet = Wallet.objects.select_for_update().get(pk=tx.wallet.pk)
                tx = Transaction.objects.select_for_update().get(pk=tx.pk)
                if tx.status == Transaction.PENDING:
                    paid_amount_pesewas = data.get('amount', 0)
                    paid_amount_ghs = paystack.pesewas_to_ghs(paid_amount_pesewas)
                    
                    balance_before = wallet.balance
                    wallet.balance += paid_amount_ghs
                    wallet.save(update_fields=['balance', 'updated_at'])
                    
                    tx.balance_before = balance_before
                    tx.balance_after = wallet.balance
                    tx.status = Transaction.COMPLETED
                    tx.meta = data
                    tx.save()
                    logger.info(f"Atomically credited GHS {paid_amount_ghs} to {wallet.user} via charge.success webhook.")

    elif event_type == 'transfer.success':
        # Complete pending withdrawal
        transfer_code = data.get('transfer_code')
        wr = WithdrawalRequest.objects.filter(transfer_code=transfer_code).first()
        if wr and wr.status in [WithdrawalRequest.PENDING, WithdrawalRequest.PROCESSING]:
            with db_tx.atomic():
                wr.status = WithdrawalRequest.COMPLETED
                wr.processed_at = timezone.now()
                wr.save()
                
                if wr.transaction:
                    wr.transaction.status = Transaction.COMPLETED
                    wr.transaction.save()
                logger.info(f"Payout completed successfully for Withdrawal Request #{wr.id}")

    elif event_type == 'transfer.failed':
        # Refund withdrawal request
        transfer_code = data.get('transfer_code')
        wr = WithdrawalRequest.objects.filter(transfer_code=transfer_code).first()
        if wr and wr.status in [WithdrawalRequest.PENDING, WithdrawalRequest.PROCESSING]:
            with db_tx.atomic():
                wr.status = WithdrawalRequest.FAILED
                wr.processed_at = timezone.now()
                wr.failure_reason = data.get('reason', 'Paystack transfer failed.')
                wr.save()
                
                if wr.transaction:
                    wr.transaction.status = Transaction.FAILED
                    wr.transaction.save()
                
                # Refund balance to user wallet
                wallet = Wallet.objects.select_for_update().get(pk=wr.wallet.pk)
                balance_before = wallet.balance
                wallet.balance += wr.amount
                wallet.save(update_fields=['balance', 'updated_at'])
                
                Transaction.objects.create(
                    wallet=wallet,
                    type=Transaction.BET_REFUND,
                    amount=wr.amount,
                    balance_before=balance_before,
                    balance_after=wallet.balance,
                    status=Transaction.COMPLETED,
                    reference=f"REF-{uuid.uuid4().hex[:12].upper()}",
                    description=f"Refund: Failed withdrawal GHS {wr.amount:.2f}",
                )
                logger.info(f"Refunded GHS {wr.amount} back to user {wallet.user} due to transfer.failed webhook.")

    return HttpResponse("OK")


def balance_partial(request):
    """HTMX endpoint – returns a styled <span> so gradient classes survive innerHTML swaps."""
    if not request.user.is_authenticated:
        return HttpResponse("")
    wallet, _ = Wallet.objects.get_or_create(user=request.user, currency='GHS')
    html = (
        f'<span class="text-2xl md:text-3xl font-black tracking-tight '
        f'text-transparent bg-clip-text bg-gradient-to-r '
        f'from-emerald-300 via-teal-200 to-cyan-300">'
        f'GHS {wallet.balance:.2f}</span>'
    )
    return HttpResponse(html)


@login_required
def list_banks(request):
    """HTMX partial returning dynamic banks selector, supporting filtering by momo or bank."""
    provider_type = request.GET.get('type')  # 'momo' or 'bank'
    banks = paystack.list_banks()
    
    if not banks:
        banks = [
            {"name": "MTN Mobile Money", "code": "MTN"},
            {"name": "Telecel Cash", "code": "VDF"},
            {"name": "AT Money", "code": "ATL"},
            {"name": "GCB Bank", "code": "GCB"},
            {"name": "Fidelity Bank Ghana", "code": "FID"},
            {"name": "Ecobank Ghana", "code": "ECO"},
            {"name": "Standard Chartered Bank", "code": "SCB"},
            {"name": "Absa Bank Ghana", "code": "ABSA"},
        ]

    momo_codes = {'MTN', 'VDF', 'VOD', 'ATL', 'AIR', 'MTN_MOMO', 'VODAFONE', 'AIRTELTIGO'}
    momo_providers = []
    bank_providers = []
    
    for b in banks:
        code = b.get('code', '').upper()
        name = b.get('name', '').lower()
        if code in momo_codes or 'mobile money' in name or 'momo' in name or 'cash' in name or 'telecel' in name or 'vodafone' in name or 'airteltigo' in name or 'at money' in name:
            momo_providers.append(b)
        else:
            bank_providers.append(b)
            
    if provider_type == 'momo':
        filtered_banks = momo_providers
        select_id = 'momo_selector'
        select_name = 'momo_code'
        placeholder = 'Select Mobile Money Network'
    elif provider_type == 'bank':
        filtered_banks = bank_providers
        select_id = 'bank_selector'
        select_name = 'bank_code'
        placeholder = 'Select Bank Account Provider'
    else:
        filtered_banks = banks
        select_id = 'bank_selector'
        select_name = 'bank_code'
        placeholder = 'Select Provider or Bank'
        
    context = {
        'banks': filtered_banks,
        'select_id': select_id,
        'select_name': select_name,
        'placeholder': placeholder,
    }
    return render(request, 'wallet/partials/banks_list.html', context)


@login_required
def verify_account(request):
    """HTMX dynamic validation of account/momo numbers."""
    account_number = request.GET.get('account_number') or request.GET.get('momo_account_number') or request.GET.get('bank_account_number')
    bank_code = request.GET.get('bank_code') or request.GET.get('momo_code')
    
    if not account_number or not bank_code:
        return HttpResponse('<div class="text-error text-xs font-semibold mt-1">Please select a provider and enter account number.</div>')

    if settings.PAYSTACK_SECRET_KEY.startswith('sk_test_mock'):
        # Mock resolution
        return HttpResponse(f'<div class="text-emerald-400 text-xs font-bold mt-1">✓ Account Verified: Demo User ({request.user.username})</div>')

    res = paystack.verify_account_number(account_number, bank_code)
    if res.get('ok'):
        # Inject the account name directly into a hidden input and show confirmation
        return HttpResponse(f"""
            <div class="text-emerald-400 text-xs font-bold mt-1">✓ Account Verified: {res['account_name']}</div>
            <input type="hidden" name="account_name" value="{res['account_name']}" />
        """)
    else:
        return HttpResponse(f'<div class="text-warning text-xs font-semibold mt-1">⚠️ Could not verify account: {res.get("message")}</div>')


@login_required
def deposit_simulate(request, reference):
    """Renders the simulated Paystack Sandbox gateway page."""
    tx = get_object_or_404(Transaction, reference=reference, type=Transaction.DEPOSIT, status=Transaction.PENDING)
    context = {
        'tx': tx,
        'wallet': tx.wallet,
    }
    return render(request, 'wallet/simulate_deposit.html', context)


@login_required
def deposit_simulate_approve(request, reference):
    """Triggers a programmatic mock charge.success webhook from the checkout simulator UI."""
    tx = get_object_or_404(Transaction, reference=reference, type=Transaction.DEPOSIT, status=Transaction.PENDING)
    
    # Construct simulated Paystack webhook payload
    webhook_payload = {
        "event": "charge.success",
        "data": {
            "reference": reference,
            "amount": int(tx.amount * 100),
            "currency": "GHS",
            "status": "success",
            "customer": {
                "email": request.user.email
            },
            "channel": "mobile_money",
            "gateway_response": "Successful"
        }
    }
    
    from django.test import RequestFactory
    rf = RequestFactory()
    mock_request = rf.post(
        '/wallet/paystack/webhook/',
        data=json.dumps(webhook_payload),
        content_type='application/json'
    )
    
    response = paystack_webhook(mock_request)
    if response.status_code == 200:
        return JsonResponse({"ok": True})
    else:
        return JsonResponse({"ok": False, "message": "Simulated webhook callback failed."})


@login_required
def withdraw_simulate(request, pk):
    """Renders the simulated live payout settlement tracker."""
    wr = get_object_or_404(WithdrawalRequest, pk=pk, wallet__user=request.user)
    context = {
        'wr': wr,
        'wallet': wr.wallet,
    }
    return render(request, 'wallet/simulate_withdraw.html', context)


@login_required
def withdraw_simulate_process(request, pk):
    """Transitions a payout request from PENDING to PROCESSING with a mock transfer code."""
    wr = get_object_or_404(WithdrawalRequest, pk=pk, wallet__user=request.user)
    if wr.status == WithdrawalRequest.PENDING:
        with db_tx.atomic():
            wr.status = WithdrawalRequest.PROCESSING
            wr.transfer_code = f"TRF-{uuid.uuid4().hex[:12].upper()}"
            wr.save()
        return JsonResponse({"ok": True, "transfer_code": wr.transfer_code})
    return JsonResponse({"ok": False, "message": f"Cannot process a request in {wr.status} state."})


@login_required
def withdraw_simulate_settle(request, pk):
    """Fires a programmatic transfer.success or transfer.failed webhook to settle or reject payout."""
    wr = get_object_or_404(WithdrawalRequest, pk=pk, wallet__user=request.user)
    status_type = request.GET.get('status', 'success')  # 'success' or 'failed'
    
    if not wr.transfer_code:
        return JsonResponse({"ok": False, "message": "Transfer has not been processed yet."})
        
    if wr.status not in [WithdrawalRequest.PENDING, WithdrawalRequest.PROCESSING]:
        return JsonResponse({"ok": False, "message": f"Transfer already in {wr.status} state."})

    # Construct simulated Paystack webhook payload
    if status_type == 'success':
        event = "transfer.success"
        event_data = {
            "transfer_code": wr.transfer_code,
            "amount": int(wr.amount * 100),
            "currency": "GHS",
            "status": "success",
            "reference": wr.transaction.reference if wr.transaction else ""
        }
    else:
        event = "transfer.failed"
        event_data = {
            "transfer_code": wr.transfer_code,
            "amount": int(wr.amount * 100),
            "currency": "GHS",
            "status": "failed",
            "reason": "Simulated banking network rejection",
            "reference": wr.transaction.reference if wr.transaction else ""
        }

    webhook_payload = {
        "event": event,
        "data": event_data
    }
    
    from django.test import RequestFactory
    rf = RequestFactory()
    mock_request = rf.post(
        '/wallet/paystack/webhook/',
        data=json.dumps(webhook_payload),
        content_type='application/json'
    )
    
    response = paystack_webhook(mock_request)
    if response.status_code == 200:
        return JsonResponse({"ok": True})
    else:
        return JsonResponse({"ok": False, "message": "Simulated webhook callback failed."})


@login_required
def withdraw_status(request, pk):
    """HTMX polling endpoint returning the live status timeline of the payout settlement."""
    wr = get_object_or_404(WithdrawalRequest, pk=pk, wallet__user=request.user)
    return render(request, 'wallet/partials/withdraw_timeline.html', {'wr': wr})
