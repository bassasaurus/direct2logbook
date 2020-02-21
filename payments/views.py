from django.shortcuts import render
import json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import stripe
from django.urls import reverse
from profile.models import Profile
from datetime import datetime
from django.contrib.auth.models import User
from logbook import settings
import os
from dotenv import load_dotenv

load_dotenv(verbose=True)


if settings.DEBUG:
    print('Stripe test key = ', settings.DEBUG)
    stripe.api_key = os.getenv('STRIPE_TEST_SECRET_KEY')
    endpoint_secret = os.getenv('endpoint_test_secret')
else:
    stripe.api_key = os.getenv('STRIPE_LIVE_SECRET_KEY')
    endpoint_secret = os.getenv('endpoint_live_secret')


@csrf_exempt
def stripe_webhook_view(request):

    # handle_payment_intent_succeeded(payment_intent)
    # elif event.type == 'payment_method.attached':
    #   payment_method = event.data.object # contains a stripe.PaymentMethod
    #   handle_payment_method_attached(payment_method)
    # ... handle other event types

    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    try:
        event = stripe.Webhook.construct_event(
          payload, sig_header, endpoint_secret
        )

    except ValueError:
        # Invalid payload
        return HttpResponse(status=400)

    except stripe.error.SignatureVerificationError:
        # Invalid signature
        return HttpResponse(status=400)

    try:
        event = stripe.Event.construct_from(
            json.loads(payload), stripe.api_key
            )
    except ValueError:
        # Invalid payload
        return HttpResponse(status=400)

    profile = Profile.objects.get(customer_id=event.data.object.customer)

    if event.type == 'checkout.session.completed':

        subscription_id = event.data.object.subscription
        # end trial
        stripe.Subscription.modify(
                    subscription_id,
                    trial_end='now',
                    cancel_at_period_end=False,
                    )

        # get new subscription_id
        subscription_response = stripe.Subscription.retrieve(subscription_id)

        timestamp = subscription_response.current_period_end
        profile.subscription_id = subscription_response.id
        profile.active = True
        profile.trial = False
        profile.canceled = False

        if subscription_response.get('items').data[0].get('plan').interval == 'month':
            profile.monthly = True
            profile.yearly = False
        elif subscription_response.get('items').data[0].get('plan').interval == 'year':
            profile.yearly = True
            profile.monthly = False
        else:
            print('subscription api changed', 'payments.views.py')

        profile.end_date = datetime.fromtimestamp(timestamp)
        profile.trial_expiring = False
        profile.save()

    elif event.type == 'customer.subscription.created':

        None

    elif event.type == 'customer.subscription.deleted':
        # print(event.type)
        profile.active = False
        profile.canceled = True
        profile.save()

    elif event.type == 'invoice.created':
        None
        # print(event.type)
        # send email receipt

    elif event.type == 'customer.subscription.trial_will_end':
        # print(event.type)
        profile.trial_expiring = True
        profile.save()
        # send email warning and make warning on login with link to profile

    elif event.type == 'customer.source.created':
        None
        # print(event.type)

    elif event.type == 'invoice.payment_succeeded':
        timestamp = event.data.object.lines['data'][0]['period']['end']
        profile.end_date = datetime.fromtimestamp(timestamp)
        profile.active = True
        profile.save()
        # send email receipt

    elif event.type == 'customer.source.created':
        None

    elif event.type == 'charge.succeeded':
        profile.active = True
        # timestamp = event.current_period_end
        # profile.end_date = datetime.fromtimestamp(timestamp)
        profile.save()

    elif event.type == 'charge.failed':
        profile.expired = True
        profile.active = False
        profile.monthly = False
        profile.yearly = False
        profile.save()

    else:
        # Unexpected event type
        print("unexpected ", event.type)
        return HttpResponse(status=400)

    return HttpResponse(status=200)


def success_view(request, user):

    user = User.objects.get(id=user)

    profile = Profile.objects.get(user=user)

    subscription_response = stripe.Subscription.retrieve(profile.subscription_id)
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


def canceled_view(request):
    context = {
        'title': 'Canceled',
        'home_link': reverse('home'),
        'parent_link': reverse('profile'),
        'parent_name': 'Profile'
    }
    return render(request, 'payments/canceled.html', context)


def subscription_cancel_view(request):

    user = request.user.pk

    profile = Profile.objects.get(user=user)

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
