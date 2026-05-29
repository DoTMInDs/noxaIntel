# -*- coding: utf-8 -*-
"""Management command to generate VAPID key pair for Web Push notifications.
Usage:
    python manage.py generate_vapid_keys
It prints the public and private keys which should be set in the .env file:
    VAPID_PUBLIC_KEY=...
    VAPID_PRIVATE_KEY=...
"""
from django.core.management.base import BaseCommand
import base64

class Command(BaseCommand):
    help = 'Generate VAPID public/private key pair for Web Push'

    def handle(self, *args, **options):
        try:
            from py_vapid import generate_vapid_private_key, generate_vapid_public_key
        except ImportError:
            self.stderr.write(self.style.ERROR('pywebpush not installed. Install with pip install pywebpush'))
            return
        private_key = generate_vapid_private_key()
        public_key = generate_vapid_public_key(private_key)
        private_b64 = base64.urlsafe_b64encode(private_key).decode('utf-8').rstrip('=')
        public_b64 = base64.urlsafe_b64encode(public_key).decode('utf-8').rstrip('=')
        self.stdout.write(self.style.SUCCESS('VAPID_PRIVATE_KEY=' + private_b64))
        self.stdout.write(self.style.SUCCESS('VAPID_PUBLIC_KEY=' + public_b64))
        self.stdout.write(self.style.NOTICE('Add these values to your .env file and restart the server.'))
