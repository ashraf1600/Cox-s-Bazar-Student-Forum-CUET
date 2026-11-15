#!/usr/bin/env bash
# Stop the deploy if any step fails (otherwise a failed migration would still go live).
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --noinput

python manage.py migrate
