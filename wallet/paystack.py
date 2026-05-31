"""
Paystack REST API client for NoxaIntel (GHS — Ghanaian Cedis).
All amounts are in Ghana Pesewas (100 pesewas = GHS 1).
"""
import hashlib
import hmac
import json
import logging
import uuid
from decimal import Decimal

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

PAYSTACK_BASE = 'https://api.paystack.co'


def _headers():
    return {
        'Authorization': f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        'Content-Type': 'application/json',
    }


def ghs_to_pesewas(amount: Decimal) -> int:
    """Convert GHS amount to integer pesewas for Paystack."""
    return int(Decimal(str(amount)) * 100)


def pesewas_to_ghs(pesewas: int) -> Decimal:
    """Convert Paystack pesewas back to GHS."""
    return Decimal(str(pesewas)) / 100


def initialize_transaction(amount_ghs: Decimal, email: str, reference: str, callback_url: str) -> dict:
    """
    Initiate a Paystack payment page for the given amount.
    Returns the Paystack authorization_url to redirect the user to.
    """
    payload = {
        'amount': ghs_to_pesewas(amount_ghs),
        'email': email,
        'reference': reference,
        'currency': 'GHS',
        'callback_url': callback_url,
        'metadata': {'platform': 'noxaintel'},
    }
    try:
        r = requests.post(f'{PAYSTACK_BASE}/transaction/initialize', json=payload, headers=_headers(), timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get('status'):
            return {'ok': True, 'authorization_url': data['data']['authorization_url'], 'reference': reference}
        return {'ok': False, 'message': data.get('message', 'Unknown error')}
    except requests.RequestException as e:
        logger.error(f'Paystack initialize_transaction error: {e}')
        return {'ok': False, 'message': str(e)}


def verify_transaction(reference: str) -> dict:
    """
    Verify a transaction by reference. Returns status and amount in GHS.
    """
    try:
        r = requests.get(f'{PAYSTACK_BASE}/transaction/verify/{reference}', headers=_headers(), timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get('status') and data['data']['status'] == 'success':
            amount_ghs = pesewas_to_ghs(data['data']['amount'])
            return {
                'ok': True,
                'amount_ghs': amount_ghs,
                'reference': reference,
                'channel': data['data'].get('channel'),
                'raw': data['data'],
            }
        return {'ok': False, 'message': data['data'].get('gateway_response', 'Payment not successful')}
    except requests.RequestException as e:
        logger.error(f'Paystack verify_transaction error: {e}')
        return {'ok': False, 'message': str(e)}


def list_banks(country: str = 'ghana') -> list:
    """Fetch list of banks supported by Paystack for Ghana."""
    try:
        r = requests.get(
            f'{PAYSTACK_BASE}/bank',
            params={'country': country, 'currency': 'GHS', 'perPage': 100},
            headers=_headers(),
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return data.get('data', [])
    except requests.RequestException as e:
        logger.error(f'Paystack list_banks error: {e}')
        return []


def _map_bank_code(bank_code: str) -> str:
    """Map internal bank/momo codes to official Paystack codes for Ghana."""
    mapping = {
        'VDF': 'VOD',         # Telecel Cash (formerly Vodafone)
        'VODAFONE': 'VOD',
        'MTN_MOMO': 'MTN',
        'AIRTELTIGO': 'ATL',
        'AIR': 'ATL',
    }
    return mapping.get(bank_code.upper(), bank_code)


def verify_account_number(account_number: str, bank_code: str) -> dict:
    """Resolve account number to get the account holder's name."""
    bank_code = _map_bank_code(bank_code)
    try:
        r = requests.get(
            f'{PAYSTACK_BASE}/bank/resolve',
            params={'account_number': account_number, 'bank_code': bank_code},
            headers=_headers(),
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if data.get('status'):
            return {'ok': True, 'account_name': data['data']['account_name']}
        return {'ok': False, 'message': data.get('message', 'Could not resolve account')}
    except requests.RequestException as e:
        logger.error(f'Paystack verify_account error: {e}')
        return {'ok': False, 'message': str(e)}


def create_transfer_recipient(bank_code: str, account_number: str, account_name: str, recipient_type: str = 'ghipss') -> dict:
    """Create a Paystack transfer recipient for a user's bank account."""
    bank_code = _map_bank_code(bank_code)
    payload = {
        'type': recipient_type,  # 'ghipss' or 'mobile_money'
        'name': account_name,
        'account_number': account_number,
        'bank_code': bank_code,
        'currency': 'GHS',
    }
    try:
        r = requests.post(f'{PAYSTACK_BASE}/transferrecipient', json=payload, headers=_headers(), timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get('status'):
            return {'ok': True, 'recipient_code': data['data']['recipient_code']}
        return {'ok': False, 'message': data.get('message', 'Could not create recipient')}
    except requests.RequestException as e:
        logger.error(f'Paystack create_transfer_recipient error: {e}')
        return {'ok': False, 'message': str(e)}


def initiate_transfer(amount_ghs: Decimal, recipient_code: str, reason: str, reference: str = None) -> dict:
    """Send money to a recipient bank account."""
    if not reference:
        reference = f"NXW-{uuid.uuid4().hex[:12].upper()}"
    payload = {
        'source': 'balance',
        'amount': ghs_to_pesewas(amount_ghs),
        'recipient': recipient_code,
        'reason': reason,
        'reference': reference,
        'currency': 'GHS',
    }
    try:
        r = requests.post(f'{PAYSTACK_BASE}/transfer', json=payload, headers=_headers(), timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get('status'):
            return {
                'ok': True,
                'transfer_code': data['data']['transfer_code'],
                'reference': reference,
                'status': data['data']['status'],
            }
        return {'ok': False, 'message': data.get('message', 'Transfer failed')}
    except requests.RequestException as e:
        logger.error(f'Paystack initiate_transfer error: {e}')
        return {'ok': False, 'message': str(e)}


def verify_webhook_signature(payload_bytes: bytes, signature: str) -> bool:
    """Verify Paystack webhook HMAC-SHA512 signature."""
    secret = settings.PAYSTACK_SECRET_KEY.encode('utf-8')
    expected = hmac.new(secret, payload_bytes, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature or '')
