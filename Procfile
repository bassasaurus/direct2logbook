web: gunicorn logbook.wsgi

worker: celery -A logbook worker -l debug --concurrency 2
