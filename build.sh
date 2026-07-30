#!/usr/bin/env bash
set -o errexit

python -m pip install -e .
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py setup_staff_roles
python manage.py seed_real_data --add-missing
python manage.py populate_history --auto --batchsize 500
python manage.py ensure_admin_user
