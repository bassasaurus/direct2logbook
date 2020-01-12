web: gunicorn logbook.wsgi


worker: celery -A /direct2logbook/logbook/celery.py --loglevel=INFO
