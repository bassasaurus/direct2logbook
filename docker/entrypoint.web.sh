#!/usr/bin/env bash
set -euo pipefail

# Database connection defaults (works with external host Postgres)
DB_HOST="${DB_HOST:-host.docker.internal}"
DB_PORT="${DB_PORT:-5432}"
DB_WAIT="${DB_WAIT:-1}"
export DB_HOST DB_PORT DB_WAIT

# Wait for Postgres (can be disabled with DB_WAIT=0)
if [[ "${DB_WAIT}" = "1" ]]; then
  echo "Waiting for Postgres at $DB_HOST:$DB_PORT..."
  until python - <<'PY'
import os, socket, time
h = os.environ.get("DB_HOST","host.docker.internal")
p = int(os.environ.get("DB_PORT","5432"))
s = socket.socket(); s.settimeout(2)
for _ in range(120):
    try:
        s.connect((h,p)); print("Postgres up"); raise SystemExit(0)
    except Exception:
        time.sleep(1)
raise SystemExit(1)
PY
  do sleep 1; done
fi

# Django: migrate + collectstatic (idempotent)
if [[ -f manage.py ]]; then
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
fi

exec gunicorn logbook.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers ${WEB_CONCURRENCY:-3} \
  --threads ${WEB_THREADS:-2} \
  --timeout ${WEB_TIMEOUT:-60} \
  --access-logfile '-' --error-logfile '-'