web: gunicorn logbook.wsgi


worker: celery -A /app/logbook/celery.py --loglevel=INFO
