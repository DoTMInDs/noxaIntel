#!/usr/bin/env bash
# Exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input

python manage.py migrate  

# Diagnostic: verify VAPID env vars are present during build
echo "=== VAPID ENV VAR CHECK ==="
python -c "import os; vk=os.environ.get('VAPID_PUBLIC_KEY',''); print(f'VAPID_PUBLIC_KEY: {vk[:25]}... (len={len(vk)})' if vk else 'VAPID_PUBLIC_KEY: *** NOT SET ***')"
python -c "import os; pk=os.environ.get('VAPID_PRIVATE_KEY',''); print(f'VAPID_PRIVATE_KEY: SET (len={len(pk)})' if pk else 'VAPID_PRIVATE_KEY: *** NOT SET ***')"
echo "==========================="

