web: gunicorn logbook.wsgi

worker: celery -A logbook.celery:app --loglevel=DEBUG
