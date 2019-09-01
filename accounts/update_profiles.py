from django.db import models
from django.contrib.auth.models import User
from accounts.models import Profile
from decouple import config
import stripe
from decouple import config
from datetime import datetime, timezone
from datetime import timedelta


def update_profiles():
    profiles = Profile.objects.all()

    for profile in profiles:

        if profile.free_access == True:
            pass
        elif len(profile.customer_id) > 0:
            pass
        else:
            user = User.objects.get(pk=profile.user.pk)
            name = '{} {}'.format(user.first_name, user.last_name )

            stripe.api_key = config('STRIPE_TEST_SECRET_KEY')

            now = datetime.now()
            trial_period = timedelta(days=14)
            end_date = now + trial_period
            timestamp = round(end_date.replace(tzinfo=timezone.utc).timestamp())

            customer_response = stripe.Customer.create(
                description=name,
                name=name,
                email=user.email
            )

        if len(profile.subscription_id) > 0:
            pass
        else:
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

            profile.customer_id=customer_response.id
            profile.subscription_id=subscription_response.id
            profile.active=False
            profile.trial=True
            profile.free_access=False
            profile.trial_expiring=False
            profile.end_date=datetime.fromtimestamp(timestamp)

        profile.save(update_fields=['customer_id', 'subscription_id', 'active', 'trial', 'free_access', 'trial_expiring', 'end_date'])
