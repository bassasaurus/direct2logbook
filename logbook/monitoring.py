"""Sentry error reporting shared by Django and Celery startup."""
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration


def configure_sentry(*, debug, dsn, environment):
    if debug or not dsn:
        return None
    return sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        # Preserve the application's existing error-reporting data policy.
        send_default_pii=True,
        traces_sample_rate=0.0,
        profiles_sample_rate=0.0,
        enable_logs=False,
    )
