from celery import shared_task
from django.contrib.auth import get_user_model

from payments.services import provision_trial


@shared_task(
    bind=True,
    max_retries=0,
    ignore_result=True,
)
def provision_trial_task(self, user_id):
    """
    Provision a Stripe trial for a verified user.

    Automatic retries are disabled because Stripe operations
    may succeed even when the worker receives an error.

    The provisioning service enforces email verification,
    idempotency, and worker ownership.
    """

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    provision_trial(user)
