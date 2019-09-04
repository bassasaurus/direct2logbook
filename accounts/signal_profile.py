from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from accounts.models import Profile
from decouple import config
import stripe
from decouple import config
from datetime import datetime, timezone
from datetime import timedelta
from flights.models import Flight, Aircraft, TailNumber, Weight, Power, Endorsement, Regs, Regs, Stat, Total

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:

        name = '{} {}'.format(instance.first_name, instance.last_name )

        stripe.api_key = config('STRIPE_TEST_SECRET_KEY')

        now = datetime.now()
        trial_period = timedelta(days=14)
        end_date = now + trial_period
        timestamp = round(end_date.replace(tzinfo=timezone.utc).timestamp())

        customer_response = stripe.Customer.create(
            description="{} {}".format(instance.first_name, instance.last_name),
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
                    "plan": "prod_FZhtiCoFBC0oJ1",
                },
            ],
            trial_end = timestamp,
        )

        timestamp = subscription_response.trial_end

        profile = Profile(
            user=instance,
            customer_id=customer_response.id,
            subscription_id=subscription_response.id,
            trial=True,
            end_date=datetime.fromtimestamp(timestamp)
        )
        profile.save()

    else:
        None

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
