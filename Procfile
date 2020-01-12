web: gunicorn logbook.wsgi


worker: celery -A /logbook/celery.py --loglevel=INFO
