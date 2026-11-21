"""Opt-in settings for an intact production backup restored on this computer."""
import os
from pathlib import Path

from decouple import config
from django.core.exceptions import ImproperlyConfigured
from operations.local_database import local_database_url

# Set these before importing base settings: it must never initialize live Stripe
# or production Sentry, even if the normal .env or shell says DEBUG=False.
os.environ['DEBUG'] = 'True'
os.environ['SENTRY_DSN'] = ''
os.environ['SENTRY_ENVIRONMENT'] = 'local-restore'
os.environ['DATABASE_URL'] = local_database_url(
    config('DATABASE_URL'), config('LOCAL_RESTORE_DATABASE_URL', default='') or None,
)

from .settings import *  # noqa: E402,F403

LOCAL_RESTORE_MODE = True
if not STRIPE_SECRET_KEY.startswith('sk_test_') or not STRIPE_PUBLISHABLE_KEY.startswith('pk_test_'):
    raise ImproperlyConfigured('Local restore settings require Stripe test secret and publishable keys.')

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_HOST = 'localhost'
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_USE_TLS = False
EMAIL_USE_SSL = False
ANYMAIL = {}
SENTRY_DSN = ''
SENTRY_ENVIRONMENT = 'local-restore'
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', '10.0.2.2'] + config(
    'LOCAL_RESTORE_ALLOWED_HOSTS', default='', cast=lambda value: [host.strip() for host in value.split(',') if host.strip()],
)
CSRF_COOKIE_DOMAIN = None
SESSION_COOKIE_DOMAIN = None
SESSION_COOKIE_NAME = 'd2l_local_restore_session'
CSRF_COOKIE_NAME = 'd2l_local_restore_csrf'
ALLAUTH_TRUSTED_PROXY_COUNT = 0

# Avoid writing to production S3 and avoid using copied cache entries at runtime.
MEDIA_ROOT = str(Path.home() / '.local/share/direct2logbook/local-media')
MEDIA_URL = '/media/'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'local-restore'}}

# The local broker and queue cannot consume the production/default task queue.
from kombu import Queue  # noqa: E402
CELERY_BROKER_URL = 'amqp://guest:guest@127.0.0.1:5672//'
CELERY_TASK_DEFAULT_QUEUE = 'd2l-local-restore-' + DATABASES['default']['NAME']
CELERY_TASK_DEFAULT_EXCHANGE = CELERY_TASK_DEFAULT_QUEUE
CELERY_TASK_DEFAULT_ROUTING_KEY = CELERY_TASK_DEFAULT_QUEUE
CELERY_TASK_QUEUES = (Queue(CELERY_TASK_DEFAULT_QUEUE, routing_key=CELERY_TASK_DEFAULT_ROUTING_KEY),)
CELERY_TASK_ROUTES = {}
CELERY_TASK_CREATE_MISSING_QUEUES = False
CELERY_TASK_ALWAYS_EAGER = False
CELERY_BEAT_SCHEDULE = {}
CELERY_BEAT_SCHEDULER = 'celery.beat.PersistentScheduler'

# Monitoring and backup jobs must not act as production jobs from this copy.
DB_BACKUP_REMOTE = ''
DB_BACKUP_ALERT_EMAIL = ''
DB_BACKUP_SENTRY_MONITOR_SLUG = ''
STRIPE_WEBHOOK_ALERT_EMAIL = ''
DISK_ALERT_EMAIL = ''
BACKGROUND_JOB_ALERT_EMAIL = ''
LOCAL_RESTORE_BACKUP_REMOTE = config('LOCAL_RESTORE_BACKUP_REMOTE', default='d2lbackups:postgresql')
LOCAL_RESTORE_RCLONE_CONFIG = config('LOCAL_RESTORE_RCLONE_CONFIG', default=str(Path.home() / '.config/rclone/d2l-backups.conf'))
LOCAL_RESTORE_STATE_DIR = config('LOCAL_RESTORE_STATE_DIR', default=str(Path.home() / '.local/share/direct2logbook/local-restore'))
