"""Synthetic configuration for isolated CI runs; never use in production."""
import os
from pathlib import Path
import tempfile

if not os.environ.get('DATABASE_URL'):
    raise RuntimeError('CI requires an explicit DATABASE_URL for an isolated database.')

_defaults = {
    'DEBUG': 'True',
    'SECRET_KEY': 'ci-only-key-not-for-production-abcdefghijklmnopqrstuvwxyz',
    'ALLOWED_HOSTS': 'localhost,127.0.0.1,testserver',
    'CSRF_TRUSTED_ORIGINS': 'http://localhost,http://testserver',
    'CSRF_COOKIE_DOMAIN': '',
    'BROKER_URL': 'memory://',
    'MEDIA_URL': '/media/',
    'AWS_ACCESS_KEY_ID': 'ci-only-access-key',
    'AWS_SECRET_ACCESS_KEY': 'ci-only-secret-key',
    'AWS_STORAGE_BUCKET_NAME': 'ci-only-bucket',
    'MAILGUN_API_KEY': 'ci-only-mailgun-key',
    'MAILGUN_API_URL': 'https://api.mailgun.net/v3/ci.invalid',
    'SENTRY_DSN': '',
    'STRIPE_TEST_SECRET_KEY': 'sk_test_ci_only',
    'STRIPE_TRIAL_PLAN_TEST': 'plan_ci_trial',
    'STRIPE_PUBLISHABLE_KEY': 'pk_test_ci_only',
    'ENDPOINT_TEST_SECRET': 'whsec_ci_only',
    'PLAN_MONTHLY_TEST': 'plan_ci_monthly',
    'PLAN_YEARLY_TEST': 'plan_ci_yearly',
    'RECAPTCHA_PUBLIC_KEY': 'ci-only-public-key',
    'RECAPTCHA_PRIVATE_KEY': 'ci-only-private-key',
}
for _name, _value in _defaults.items():
    os.environ[_name] = _value

from .settings import *  # noqa: E402,F403

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
CELERY_BROKER_URL = 'memory://'
CELERY_TASK_ALWAYS_EAGER = False
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
STATIC_ROOT = str(Path(tempfile.gettempdir()) / 'direct2logbook-ci-static')
MEDIA_ROOT = str(Path(tempfile.gettempdir()) / 'direct2logbook-ci-media')
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
DB_BACKUP_REMOTE = ''
DB_BACKUP_SENTRY_MONITOR_SLUG = ''
DB_BACKUP_ALERT_EMAIL = ''
STRIPE_WEBHOOK_ALERT_EMAIL = ''
