#!/usr/bin/env bash
set -o errexit

python -m pip install -e .
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py setup_staff_roles
python manage.py seed_real_data --add-missing
python manage.py enrich_asset_profiles
python manage.py apply_catalog_reviews
python manage.py apply_catalog_reviews --reviews data/asset_editorial_reviews_2026_08_24.json
python manage.py apply_catalog_reviews --reviews data/asset_editorial_reviews_2026_08_24_expansion.json
python manage.py scan_asset_duplicates
python manage.py populate_history --auto --batchsize 500
python manage.py ensure_admin_user
