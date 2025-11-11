# syntax=docker/dockerfile:1.6

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# System deps
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential curl libpq-dev gettext \
    && rm -rf /var/lib/apt/lists/*

# Create user
RUN useradd -m -u 10001 appuser

WORKDIR /app

# Use a separate layer for deps to maximize cache
FROM base AS deps
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt

# Final image
FROM base AS runtime
# Copy installed site-packages from deps
COPY --from=deps /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=deps /usr/local/bin /usr/local/bin

# App code
COPY . /app

# Static/media directories (bind as volumes in compose if you prefer)
RUN mkdir -p /app/staticfiles /app/media && chown -R appuser:appuser /app
USER appuser

# Healthcheck script (optional: checks Gunicorn port)
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD \
    python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1',8000)); print('ok')" || exit 1

EXPOSE 8000

# Default command is overridden by compose services (web/worker/beat)
CMD ["bash", "-lc", "gunicorn logbook.wsgi:application --bind 0.0.0.0:8000 --workers 3 --threads 2 --timeout 60"]