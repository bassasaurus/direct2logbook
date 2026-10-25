"""Verify delivery in the view; reconcile signed notifications against Stripe."""
from collections.abc import Mapping
from datetime import datetime, timezone

import stripe
from django.conf import settings
from django.db import transaction
from django.utils import timezone as django_timezone

from payments.models import StripeWebhookEvent
from profile.models import Profile


SUBSCRIPTION_EVENTS = {
    'customer.subscription.created', 'customer.subscription.updated',
    'customer.subscription.deleted', 'customer.subscription.trial_will_end',
    'customer.subscription.paused', 'customer.subscription.resumed',
}
INVOICE_EVENTS = {'invoice.payment_succeeded', 'invoice.paid', 'invoice.payment_failed'}
CHECKOUT_EVENTS = {'checkout.session.completed', 'checkout.session.async_payment_succeeded'}
HANDLED_EVENTS = SUBSCRIPTION_EVENTS | INVOICE_EVENTS | CHECKOUT_EVENTS


class InvalidWebhook(ValueError):
    pass


class WebhookReconciliationError(Exception):
    """Return a non-2xx response so Stripe can deliver this event again."""


def stripe_id(value):
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return value.get('id')
    return None


def invoice_subscription(invoice):
    # Support both the legacy and newer Stripe invoice payload shapes.
    direct = stripe_id(invoice.get('subscription'))
    if direct:
        return direct
    parent = invoice.get('parent') or {}
    return stripe_id((parent.get('subscription_details') or {}).get('subscription'))


def subscription_state(subscription):
    status = subscription.get('status')
    if status not in {'active', 'trialing', 'past_due', 'unpaid', 'canceled',
                      'incomplete', 'incomplete_expired', 'paused'}:
        raise WebhookReconciliationError('Unrecognized subscription status')
    items = (subscription.get('items') or {}).get('data') or []
    period_end = subscription.get('current_period_end')
    if status == 'trialing':
        period_end = subscription.get('trial_end') or period_end
    if not period_end:
        periods = [item.get('current_period_end') for item in items
                   if isinstance(item.get('current_period_end'), int)]
        period_end = min(periods) if periods else None
    if status in {'active', 'trialing'} and not isinstance(period_end, int):
        raise WebhookReconciliationError('Subscription has no billing period end')
    intervals = set()
    for item in items:
        recurring = (item.get('price') or {}).get('recurring') or {}
        interval = recurring.get('interval') or (item.get('plan') or {}).get('interval')
        if interval:
            intervals.add(interval)
    return status, period_end, intervals


@transaction.atomic
def process_stripe_webhook(event):
    if not isinstance(event, Mapping):
        raise InvalidWebhook('Expected an event object')
    event_id, event_type = event.get('id'), event.get('type')
    if not isinstance(event_id, str) or not event_id or not isinstance(event_type, str):
        raise InvalidWebhook('Missing event identity')
    if event_type not in HANDLED_EVENTS:
        # Charges and one-off payments do not determine subscription access.
        return 'ignored'
    obj = (event.get('data') or {}).get('object')
    if not isinstance(obj, Mapping):
        raise InvalidWebhook('Missing event object')

    receipt, created = StripeWebhookEvent.objects.get_or_create(
        event_id=event_id, defaults={'event_type': event_type},
    )
    if not created:
        return 'duplicate'

    checkout = event_type in CHECKOUT_EVENTS
    if checkout:
        subscription_id = stripe_id(obj.get('subscription'))
        if obj.get('mode') != 'subscription' or obj.get('payment_status') not in {'paid', 'no_payment_required'}:
            receipt.outcome = 'ignored'
            receipt.save(update_fields=['outcome'])
            return 'ignored'
    elif event_type in INVOICE_EVENTS:
        subscription_id = invoice_subscription(obj)
        if not subscription_id:
            receipt.outcome = 'ignored'
            receipt.save(update_fields=['outcome'])
            return 'ignored'
    else:
        subscription_id = stripe_id(obj.get('id'))

    customer_id = stripe_id(obj.get('customer'))
    if not customer_id or not subscription_id:
        raise InvalidWebhook('Missing billing identity')
    # Serialize all billing updates for this customer. Fetch canonical Stripe
    # state AFTER taking the lock, so concurrently delivered snapshots cannot
    # overwrite each other with stale event data.
    try:
        profile = Profile.objects.select_for_update().get(customer_id=customer_id)
    except (Profile.DoesNotExist, Profile.MultipleObjectsReturned) as exc:
        raise WebhookReconciliationError('Customer mapping not ready or ambiguous') from exc

    if not checkout and profile.subscription_id != subscription_id:
        if not profile.subscription_id:
            # Provisioning may still be persisting its new Stripe subscription.
            raise WebhookReconciliationError('Subscription mapping not ready')
        receipt.outcome = 'ignored_old_subscription'
        receipt.save(update_fields=['outcome'])
        return receipt.outcome

    subscription = stripe.Subscription.retrieve(
        subscription_id, api_key=settings.STRIPE_SECRET_KEY,
    )
    if stripe_id(subscription.get('customer')) != customer_id or subscription.get('id') != subscription_id:
        raise WebhookReconciliationError('Stripe subscription does not match customer')

    if checkout and profile.subscription_id and profile.subscription_id != subscription_id:
        current = stripe.Subscription.retrieve(
            profile.subscription_id, api_key=settings.STRIPE_SECRET_KEY,
        )
        if stripe_id(current.get('customer')) != customer_id:
            raise WebhookReconciliationError('Current subscription customer mismatch')
        incoming_created, current_created = subscription.get('created'), current.get('created')
        if not isinstance(incoming_created, int) or not isinstance(current_created, int):
            raise WebhookReconciliationError('Cannot determine subscription chronology')
        if incoming_created < current_created:
            receipt.outcome = 'ignored_old_subscription'
            receipt.save(update_fields=['outcome'])
            return receipt.outcome
        if incoming_created == current_created:
            raise WebhookReconciliationError('Subscription chronology needs manual review')

    status, period_end, intervals = subscription_state(subscription)
    trial = status == 'trialing'
    profile.subscription_id = subscription_id
    profile.active = status == 'active'
    profile.expired = status not in {'active', 'trialing'}
    profile.trial = trial
    profile.canceled = status == 'canceled' or (
        bool(subscription.get('cancel_at_period_end')) and not trial
    )
    profile.monthly = not trial and intervals == {'month'}
    profile.yearly = not trial and intervals == {'year'}
    trial_end = subscription.get('trial_end')
    profile.trial_expiring = bool(
        trial and isinstance(trial_end, int)
        and 0 < trial_end - django_timezone.now().timestamp() <= 3 * 24 * 60 * 60
    )
    if isinstance(period_end, int):
        profile.end_date = datetime.fromtimestamp(period_end, tz=timezone.utc).date()
    profile.save(update_fields=[
        'subscription_id', 'active', 'expired', 'trial', 'canceled',
        'monthly', 'yearly', 'trial_expiring', 'end_date',
    ])
    # The receipt and profile update commit together. Any exception rolls both
    # back, leaving the exact same event eligible for a later Stripe retry.
    return 'processed'
