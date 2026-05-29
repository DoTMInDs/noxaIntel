import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone


class Wallet(models.Model):
    """Each user has exactly one wallet holding their GHS balance."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wallet',
    )
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=5, default='GHS')
    is_locked = models.BooleanField(default=False, help_text='Lock withdrawals during review')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Wallet'
        verbose_name_plural = 'Wallets'

    def __str__(self):
        return f"{self.user} — GHS {self.balance}"

    def credit(self, amount: Decimal, tx_type: str, description: str, reference: str = None, meta: dict = None):
        """Atomically credit the wallet and create a Transaction record."""
        from django.db import transaction as db_tx
        with db_tx.atomic():
            wallet = Wallet.objects.select_for_update().get(pk=self.pk)
            balance_before = wallet.balance
            wallet.balance += Decimal(str(amount))
            wallet.save(update_fields=['balance', 'updated_at'])
            tx = Transaction.objects.create(
                wallet=wallet,
                type=tx_type,
                amount=amount,
                balance_before=balance_before,
                balance_after=wallet.balance,
                status=Transaction.COMPLETED,
                reference=reference or str(uuid.uuid4()),
                description=description,
                meta=meta or {},
            )
            self.refresh_from_db()
            return tx

    def debit(self, amount: Decimal, tx_type: str, description: str, reference: str = None, meta: dict = None):
        """Atomically debit the wallet; raises ValueError if insufficient funds."""
        from django.db import transaction as db_tx
        with db_tx.atomic():
            wallet = Wallet.objects.select_for_update().get(pk=self.pk)
            amount = Decimal(str(amount))
            if wallet.balance < amount:
                raise ValueError(f"Insufficient balance: GHS {wallet.balance} < GHS {amount}")
            balance_before = wallet.balance
            wallet.balance -= amount
            wallet.save(update_fields=['balance', 'updated_at'])
            tx = Transaction.objects.create(
                wallet=wallet,
                type=tx_type,
                amount=amount,
                balance_before=balance_before,
                balance_after=wallet.balance,
                status=Transaction.COMPLETED,
                reference=reference or str(uuid.uuid4()),
                description=description,
                meta=meta or {},
            )
            self.refresh_from_db()
            return tx


class Transaction(models.Model):
    # Types
    DEPOSIT = 'DEPOSIT'
    WITHDRAWAL = 'WITHDRAWAL'
    BET_STAKE = 'BET_STAKE'
    BET_WIN = 'BET_WIN'
    BET_REFUND = 'BET_REFUND'
    CASHOUT = 'CASHOUT'
    BONUS = 'BONUS'
    TYPE_CHOICES = [
        (DEPOSIT, 'Deposit'),
        (WITHDRAWAL, 'Withdrawal'),
        (BET_STAKE, 'Bet Stake'),
        (BET_WIN, 'Bet Winnings'),
        (BET_REFUND, 'Bet Refund'),
        (CASHOUT, 'Cash Out'),
        (BONUS, 'Bonus'),
    ]

    # Statuses
    PENDING = 'PENDING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    REVERSED = 'REVERSED'
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (COMPLETED, 'Completed'),
        (FAILED, 'Failed'),
        (REVERSED, 'Reversed'),
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    balance_before = models.DecimalField(max_digits=14, decimal_places=2)
    balance_after = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    reference = models.CharField(max_length=120, unique=True, db_index=True)
    description = models.CharField(max_length=255, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', 'type']),
            models.Index(fields=['wallet', 'status']),
        ]

    def __str__(self):
        return f"{self.type} GHS {self.amount} [{self.status}] — {self.reference[:12]}"

    @property
    def is_credit(self):
        return self.type in (self.DEPOSIT, self.BET_WIN, self.BET_REFUND, self.CASHOUT, self.BONUS)


class WithdrawalRequest(models.Model):
    PENDING = 'PENDING'
    PROCESSING = 'PROCESSING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (PROCESSING, 'Processing'),
        (COMPLETED, 'Completed'),
        (FAILED, 'Failed'),
    ]

    MOBILE_MONEY = 'MOBILE_MONEY'
    BANK = 'BANK'
    PAYOUT_CHANNEL_CHOICES = [
        (MOBILE_MONEY, 'Mobile Money'),
        (BANK, 'Bank Transfer'),
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='withdrawal_requests')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payout_type = models.CharField(max_length=20, choices=PAYOUT_CHANNEL_CHOICES, default=BANK)
    bank_name = models.CharField(max_length=100)
    bank_code = models.CharField(max_length=20)
    account_number = models.CharField(max_length=20)
    account_name = models.CharField(max_length=120)
    paystack_recipient_code = models.CharField(max_length=100, blank=True)
    transfer_code = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    failure_reason = models.CharField(max_length=255, blank=True)
    transaction = models.OneToOneField(
        Transaction, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='withdrawal_request',
    )
    requested_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"Withdrawal GHS {self.amount} → {self.account_name} [{self.status}]"
