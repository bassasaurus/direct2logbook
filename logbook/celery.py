from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv(verbose=True)

# start worker:
# celery -A logbook worker -l info --concurrency 2 --without-gossip --without-mingle --without-heartbeat
# http://localhost:15672/

# heroku logs -t -p worker

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'logbook.settings')

app = Celery('logbook', broker=os.getenv('CLOUDAMQP_URL'))

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('logbook.celery_config')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))
