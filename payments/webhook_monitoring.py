import logging

from django.db.models import F
from django.utils import timezone

from payments.models import StripeWebhookFailure


logger = logging.getLogger('django.payments.webhooks')


def record_webhook_failure(event):
    """Run outside reconciliation's transaction; monitoring must not change HTTP status."""
    event_id, event_type = event.get('id'), event.get('type')
    if not isinstance(event_id, str) or not isinstance(event_type, str):
        return
    if not event_id or len(event_id) > 255 or len(event_type) > 255:
        return
    try:
        failure, _ = StripeWebhookFailure.objects.get_or_create(
            event_id=event_id,
            defaults={'event_type': event_type, 'last_failed_at': timezone.now()},
        )
        StripeWebhookFailure.objects.filter(pk=failure.pk).update(
            attempts=F('attempts') + 1, last_failed_at=timezone.now(),
        )
    except Exception:
        logger.exception('Could not record Stripe webhook failure')
