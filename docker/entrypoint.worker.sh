#!/usr/bin/env bash
set -euo pipefail
# Optional: wait for broker and DB
exec celery -A logbook worker --loglevel=${CELERY_LOGLEVEL:-INFO} --concurrency=${CELERY_CONCURRENCY:-4}