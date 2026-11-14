"""Create hosted Checkout only for an authenticated, explicit plan selection."""
import logging
from urllib.parse import urlsplit

import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from profile.models import Profile
from payments.models import BillingProvisioning

SALT = 'payments.checkout-request'
logger = logging.getLogger(__name__)


def create_session(request, customer_id, price_id, request_key):
    return stripe.checkout.Session.create(
        customer=customer_id, mode='subscription',
        line_items=[{'price': price_id, 'quantity': 1}],
        payment_method_types=['card'],
        success_url=request.build_absolute_uri(reverse('payment_success', args=[request.user.pk])),
        cancel_url=request.build_absolute_uri(reverse('payment_canceled', args=[request.user.pk])),
        client_reference_id=str(request.user.pk),
        metadata={'direct2logbook_user_id': str(request.user.pk)},
        subscription_data={'metadata': {'direct2logbook_user_id': str(request.user.pk)}},
        idempotency_key=request_key, api_key=settings.STRIPE_SECRET_KEY,
    )


def unavailable(request, message, status=400, retry=False):
    return render(request, 'payments/checkout_unavailable.html', {
        'title': 'Checkout unavailable', 'page_title': 'Checkout',
        'parent_link': reverse('profile'), 'parent_name': 'Profile',
        'checkout_message': message, 'retry_checkout': retry,
        'checkout_request': request.POST.get('checkout_request', ''),
        'plan': request.POST.get('plan', ''),
    }, status=status)


@login_required
@require_POST
@csrf_protect
@never_cache
def start_checkout(request):
    plan = request.POST.get('plan')
    prices = {'monthly': settings.PLAN_MONTHLY, 'yearly': settings.PLAN_YEARLY}
    if plan not in prices:
        return unavailable(request, 'Choose the monthly or yearly plan.')
    try:
        intent = signing.loads(request.POST.get('checkout_request', ''), salt=SALT, max_age=3600)
        if intent.get('user') != request.user.pk or not isinstance(intent.get('nonce'), str) or len(intent['nonce']) != 32:
            raise signing.BadSignature('Invalid checkout request')
    except (signing.BadSignature, ValueError, TypeError, AttributeError):
        return unavailable(request, 'This checkout request has expired or is invalid. Return to your profile and choose a plan again.')
    try:
        with transaction.atomic():
            profile = get_object_or_404(Profile.objects.select_for_update(), user=request.user)
            if profile.free_access:
                return unavailable(request, 'Your account already has free access. No subscription is needed.', 409)
            if not (profile.customer_id and profile.subscription_id and profile.end_date):
                return unavailable(request, 'Your billing account is still being set up. Please try again from your profile shortly.', 409)
            billing = BillingProvisioning.objects.filter(user=request.user).first()
            if billing and (billing.status == BillingProvisioning.Status.PROCESSING or billing.outcome_uncertain):
                return unavailable(request, 'Your billing account needs confirmation before checkout. Please contact support.', 409)
            # Check Stripe too: a recent purchase may not yet have reached the webhook.
            subscriptions = stripe.Subscription.list(
                customer=profile.customer_id, status='all', limit=100, api_key=settings.STRIPE_SECRET_KEY)
            for subscription in subscriptions.auto_paging_iter():
                if subscription.get('status') not in {'canceled', 'incomplete_expired'}:
                    if subscription.get('status') == 'trialing' and subscription.get('id') == profile.subscription_id:
                        continue
                    return unavailable(request, 'A subscription already exists for your account. Return to your profile to review its status.', 409)
            session = create_session(request, profile.customer_id, prices[plan],
                                     f"d2l-checkout-{request.user.pk}-{intent['nonce']}-{plan}")
            url = session.get('url')
            parts = urlsplit(url) if isinstance(url, str) else None
            if not parts or parts.scheme != 'https' or parts.netloc != 'checkout.stripe.com' or not parts.path.startswith('/'):
                raise ValueError('Invalid hosted checkout URL')
    except (stripe.error.StripeError, ValueError):
        logger.exception('Checkout could not start for user_id=%s', request.user.pk)
        return unavailable(request, 'Checkout is temporarily unavailable. Please try again. Your subscription has not been changed by this request.', 503, retry=True)
    response = HttpResponse(status=303)
    response['Location'] = url
    return response
