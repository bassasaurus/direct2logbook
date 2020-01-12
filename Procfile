web: gunicorn logbook.wsgi

worker: celery -A logbook.celery --loglevel=INFO
