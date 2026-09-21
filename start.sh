#!/usr/bin/env bash
set -euo pipefail

# Free Render services cannot run a dedicated pre-deploy command.
bash release.sh
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}"
