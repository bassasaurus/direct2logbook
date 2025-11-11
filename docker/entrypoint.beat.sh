#!/usr/bin/env bash
set -euo pipefail
exec celery -A logbook beat --loglevel=${CELERY_LOGLEVEL:-INFO}