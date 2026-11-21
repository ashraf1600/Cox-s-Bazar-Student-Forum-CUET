#!/usr/bin/env bash
# Stop the deploy if any step fails (otherwise a failed migration would still go live).
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --noinput

python manage.py migrate

# Creates the admin account from DJANGO_ADMIN_EMAIL / DJANGO_ADMIN_PASSWORD (skipped if unset).
python manage.py ensure_admin

# Prints what is still missing for launch. Never fails the deploy.
python manage.py launch_check || true
