from django.shortcuts import render
import json
from django.http import HttpResponse
from decouple import config
from django.views.decorators.csrf import csrf_exempt
import stripe
from django.urls import reverse
from accounts.models import Profile
from datetime import datetime
from django.contrib.auth.models import User

stripe.api_key = config('STRIPE_TEST_SECRET_KEY')

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

    profile = Profile.objects.get(customer_id = event.data.object.customer)

    if event.type == 'checkout.session.completed' or 'charge.succeeded':
        print(event.type)
        subscription_id = event.data.object.subscription
        #end trial
        modified_subscription_response = stripe.Subscription.modify(subscription_id,
                    trial_end='now',
                    days_until_due = 0,
                    )

        subscription_response = stripe.Subscription.retrieve(subscription_id)

        timestamp = subscription_response.current_period_end
        profile.active = True
        profile.trial = False
        profile.end_date = datetime.fromtimestamp(timestamp)
        profile.trial_expiring = False
        profile.save()

    # handle_payment_intent_succeeded(payment_intent)
    # elif event.type == 'payment_method.attached':
    #   payment_method = event.data.object # contains a stripe.PaymentMethod
    #   handle_payment_method_attached(payment_method)
    # ... handle other event types
    elif event.type == 'customer.created':
        None
    elif event.type == 'customer.subscription.created':
        None
    elif event.type == 'customer.subscription.deleted':
        print(event.type)
        profile.active = False
        profile.save()
        #make account/user inactive
    elif event.type == 'invoice.created':
        None
        # print(event.type)
        #send email receipt
    elif event.type == 'customer.subscription.trial_will_end':
        print(event.type)
        profile.trial_expiring = True
        profile.save()
        #send email warning and make warning on login with link to profile
    elif event.type == 'invoice.created':
        None
        #happens again in webhook flow -- not sure how to handle
        # print(event.type)
        #send email receipt
    elif event.type == 'invoice.payment_succeeded':
        None
        # print(event.type)
    elif event.type == 'customer.source.created':
        None

    else:
        # Unexpected event type
        print("unexpected ", event.type)
        return HttpResponse(status=400)

    return HttpResponse(status=200)

def success_view(request, user):

    user = User.objects.get(id=user)

    profile = Profile.objects.get(user=user)

    subscription_response = stripe.Subscription.retrieve(profile.subscription_id)
    print(subscription_response)

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
