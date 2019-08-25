from django.shortcuts import render
import json
from django.http import HttpResponse
from decouple import config
from django.views.decorators.csrf import csrf_exempt
import stripe
from django.urls import reverse
from accounts.models import Profile

stripe.api_key = config('STRIPE_TEST_SECRET_KEY')

def subscribe_view(request):
    user = request.user

    customer_id = Profile.objects.get(user=user).customer_id

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=['card'],
        subscription_data={
            'items': [{
            'plan': 'plan_FZhtfxftM44uHz',
            }],
        },
    success_url='https://www.direct2logbook.com/payments/success',
    cancel_url='https://www.direct2logbook.com/payments/cancel',
    )
    context = {
        'CHECKOUT_SESSION_ID': session.id,
        'STRIPE_TEST_PUBLISHABLE_KEY': config('STRIPE_TEST_PUBLISHABLE_KEY')
    }

    print(session.id)
    return render(request, 'payments/subscribe.html', context)

@csrf_exempt
def stripe_webhook_view(request):
    payload = request.body
    event = None

    try:
        event = stripe.Event.construct_from(
        json.loads(payload), stripe.api_key
        )
    except ValueError as e:
        # Invalid payload
        return HttpResponse(status=400)

        # Handle the event
    if event.type == 'checkout.session.completed':
        payment_intent = event.data.object # contains a stripe.PaymentIntent
    # handle_payment_intent_succeeded(payment_intent)
    # elif event.type == 'payment_method.attached':
    #   payment_method = event.data.object # contains a stripe.PaymentMethod
    #   handle_payment_method_attached(payment_method)
    # ... handle other event types
    elif event.type == 'customer.created':
        print(event.data.object.id)
        #add customer id to profile
    elif event.type == 'customer.source.created':
        print(event.type)
    elif event.type == 'customer.subscription.created':
        print(event.type)
    elif event.type == 'customer.subscription.deleted':
        print(event.type)
        #make account/user inactive
    elif event.type == 'invoice.created':
        print(event.type)
        #send email receipt
    elif event.type == 'customer.subscription.trial_will_end':
        print(event.type)
        #send email warning and make warning on login with link to profile
    #happens again in webhook flow -- not sure how to handle
    elif event.type == 'invoice.created':
        print(event.type)
        #send email receipt
    elif event.type == 'invoice.payment_succeeded':
        print(event.type)
    elif event.type == 'charge.succeeded':
        print(event.type)

    else:
        # Unexpected event type
        print("unexpected ", event.type)
        return HttpResponse(status=400)

    return HttpResponse(status=200)

def success_view(request):
    context = {
        'title': 'Success',
        'home_link': reverse('home'),
        'parent_link': reverse('profile'),
        'parent_name': 'Profile'
    }
    return render(request,'payments/success.html', context)

def canceled_view(request):
    context = {
        'title': 'Canceled',
        'home_link': reverse('home'),
        'parent_link': reverse('profile'),
        'parent_name': 'Profile'
    }
    return render(request,'payments/canceled.html', context)

def debug_view(request):
    context = {
    }
    return render(request,'payments/debug.html', context)
