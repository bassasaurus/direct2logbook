import logging
from functools import partial

from allauth.account.signals import email_confirmed
from django.db import transaction
from django.dispatch import receiver
from kombu.exceptions import OperationalError

from payments.tasks import provision_trial_task


logger = logging.getLogger("django.payments")


def publish_trial_provisioning(user_id):
    """Leave verified accounts intact if the broker cannot accept the task."""
    try:
        provision_trial_task.apply_async(args=(user_id,), retry=False)
    except OperationalError:
        # A publish error does not prove the broker never received the task.
        # Keep recovery manual; the service guards existing/uncertain attempts.
        logger.exception(
            "Could not queue trial provisioning for user_id=%s. "
            "Email verification remains saved. Delivery may be uncertain; "
            "inspect billing provisioning before manual recovery.",
            user_id,
        )


@receiver(email_confirmed, dispatch_uid="payments.queue_trial_after_email_confirmation")
def queue_trial_after_email_confirmation(sender, request, email_address, **kwargs):
    """Queue billing only after the verified email transaction commits."""
    if not email_address.verified:
        return

    transaction.on_commit(
        partial(publish_trial_provisioning, email_address.user_id),
        using=email_address._state.db,
    )
