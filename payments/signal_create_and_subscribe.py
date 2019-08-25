from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from accounts.models import Profile
import stripe
from decouple import config
from datetime import date

@receiver(post_save, sender=User)
def create_customer(sender, instance, created, **kwargs):
    name = '{} {}'.format(instance.first_name, instance.last_name )

    user = instance.pk

    user = User.objects.get(pk=user)

    profile = Profile.objects.get(user=user)

    stripe.api_key = config('STRIPE_TEST_SECRET_KEY')

    customer_response = stripe.Customer.create(
        description="New Customer",
        name=name,
        email=instance.email
    )

    subscription_response = stripe.Subscription.create(
        customer=customer_response.id,
        trial_from_plan=True,
        items=[
            {
                "plan": "plan_FZhtfxftM44uHz",
            },
        ]
    )

    timestamp = subscription_response.trial_end
    
    profile.trial_end = date.fromtimestamp(timestamp)
    profile.customer_id = customer_response.id
    profile.save()
