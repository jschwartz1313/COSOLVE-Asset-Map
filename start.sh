#!/usr/bin/env bash
set -euo pipefail

# Free Render services cannot run a dedicated pre-deploy command.
python manage.py release_database
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}"
