from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from accounts.models import Profile
import stripe
from decouple import config
from datetime import datetime, timezone
from datetime import timedelta

@receiver(post_save, sender=User)
def create_and_subscribe(sender, instance, created, **kwargs):
    name = '{} {}'.format(instance.first_name, instance.last_name )

    user = instance.pk

    user = User.objects.get(pk=user)

    profile = Profile.objects.get(user=user)

    stripe.api_key = config('STRIPE_TEST_SECRET_KEY')

    now = datetime.now()
    trial_period = timedelta(days=14)
    end_date = now + trial_period
    timestamp = round(end_date.replace(tzinfo=timezone.utc).timestamp())
    print(end_date, timestamp)

    customer_response = stripe.Customer.create(
        description="New Customer",
        name=name,
        email=instance.email
    )

    subscription_response = stripe.Subscription.create(
        customer=customer_response.id,
        collection_method = "send_invoice",
        days_until_due = 14,
        cancel_at_period_end=True,
        items=[
            {
                "plan": "plan_FZhtfxftM44uHz",
            },
        ],
        trial_end = timestamp,
    )

    timestamp = subscription_response.trial_end
    if created == True:
        profile.customer_id = customer_response.id
        profile.subscription_id = subscription_response.id
        profile.trial_end = datetime.fromtimestamp(subscription_response.trial_end)
        profile.save()
        print("created = True")
    else:
        None
