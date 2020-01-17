web: gunicorn logbook.wsgi

worker: celery -A logbook worker -l info --concurrency 2
