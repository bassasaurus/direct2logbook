from .base import *
import os
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from decouple import config

DEBUG = False

sentry_sdk.init(
    dsn="https://e3f79fa21e484fe6b58a2e227a5bbce5@sentry.io/1515848",
    integrations=[DjangoIntegration(), CeleryIntegration()]
)

ANYMAIL = {
    # (exact settings here depend on your ESP...)
    "MAILGUN_API_KEY": config('MAILGUN_API_KEY'),
    "MAILGUN_SENDER_DOMAIN": 'mg.direct2logbook.com',  # your Mailgun domain, if needed
}
# or sendgrid.EmailBackend, or...
EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
# if you don't already have this in settings
DEFAULT_FROM_EMAIL = "no-reply@direct2logbook.com"
