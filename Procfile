web: gunicorn logbook.wsgi

worker: celery -A logbook.celery:app --loglevel=DEBUG --concurrency=2 --app direct2logbook
