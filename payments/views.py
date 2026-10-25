from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST
import stripe
from django.urls import reverse
from profile.models import Profile
from datetime import datetime
from django.contrib.auth.models import User
from django.conf import settings
from payments.webhooks import InvalidWebhook, process_stripe_webhook

stripe.api_key = settings.STRIPE_SECRET_KEY


logger = logging.getLogger('django.payments.webhooks')


@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    signature = request.META.get('HTTP_STRIPE_SIGNATURE')
    if not signature:
        return HttpResponse(status=400)
    try:
        event = stripe.Webhook.construct_event(
            request.body, signature, settings.ENDPOINT_SECRET_KEY,
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    try:
        process_stripe_webhook(event)
    except InvalidWebhook:
        logger.warning('Malformed signed Stripe event rejected')
        return HttpResponse(status=400)
    except Exception:
        # Never acknowledge failed processing: Stripe should retry delivery.
        logger.exception('Stripe webhook processing failed for event_id=%s', event.get('id'))
        return HttpResponse(status=503)
    return HttpResponse(status=200)


@login_required
def success_view(request, user):
    # Authorize the URL ID before making any request to Stripe.
    user = get_object_or_404(User.objects.filter(pk=request.user.pk), pk=user)
    profile = get_object_or_404(
        Profile.objects.exclude(subscription_id=''), user=user,
    )

    subscription_response = stripe.Subscription.retrieve(
        profile.subscription_id)
    # print(subscription_response)
    timestamp = subscription_response.current_period_end
    end_date = datetime.fromtimestamp(timestamp)

    context = {
        'title': 'Success',
        'home_link': reverse('home'),
        'parent_link': reverse('profile'),
        'parent_name': 'Profile',
        'response': subscription_response,
        'nickname': subscription_response.plan.nickname,
        'end_date': end_date
    }

    return render(request, 'payments/success.html', context)


def canceled_view(request, user):
    context = {
        'title': 'Canceled',
        'home_link': reverse('home'),
        'parent_link': reverse('profile'),
        'parent_name': 'Profile'
    }
    return render(request, 'payments/canceled.html', context)


@login_required
@require_POST
@csrf_protect
def subscription_cancel_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    if not profile.subscription_id:
        return HttpResponse("No subscription is available to cancel.", status=400)

    canceled_subscription_response = stripe.Subscription.modify(
        profile.subscription_id,
        cancel_at_period_end=True
    )

    profile.canceled = True
    profile.active = False
    profile.save()

    timestamp = canceled_subscription_response.current_period_end
    end_date = datetime.fromtimestamp(timestamp)

    context = {
        'title': 'Subscription canceled',
        'home_link': reverse('home'),
        'parent_link': reverse('profile'),
        'parent_name': 'Profile',

        'end_date': end_date,
    }

    return render(request, 'payments/subscription_canceled.html', context)
