from django.shortcuts import render
import json
from django.http import HttpResponse
from decouple import config
from django.views.decorators.csrf import csrf_exempt
import stripe
from django.views.generic import TemplateView
from django.urls import reverse


stripe.api_key = config('STRIPE_TEST_SECRET_KEY')

# endpoint_secret = 'whsec_0PhWIPlbu61crYCy1xq0uG0QBalnesIO'

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
  if event.type == 'checkout.session.completed' or 'subscription_schedule.completed':
    payment_intent = event.data.object # contains a stripe.PaymentIntent
    # handle_payment_intent_succeeded(payment_intent)
  # elif event.type == 'payment_method.attached':
  #   payment_method = event.data.object # contains a stripe.PaymentMethod
  #   handle_payment_method_attached(payment_method)
  # ... handle other event types
  else:
    # Unexpected event type
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
