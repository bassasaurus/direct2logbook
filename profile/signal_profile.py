from django.contrib.auth.models import User, Group
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Profile
import stripe
from datetime import datetime, timezone
from datetime import timedelta
from flights.models import Total
from logbook import settings
from decouple import config


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):

    if created:

        name = '{} {}'.format(instance.first_name, instance.last_name)

        if settings.DEBUG:
            stripe.api_key = config('STRIPE_TEST_SECRET_KEY')
        else:
            stripe.api_key = config('STRIPE_LIVE_SECRET_KEY')

        now = datetime.now()
        trial_period = timedelta(days=14)
        end_date = now + trial_period
        timestamp = round(end_date.replace(tzinfo=timezone.utc).timestamp())

        customer_response = stripe.Customer.create(
            description="{} {}".format(
                instance.first_name, instance.last_name),
            name=name,
            email=instance.email
        )

        if settings.DEBUG:
            plan = 'plan_FkX07tGXr4f3Mh'  # test mode trial
        else:
            plan = 'plan_Fkf5ex0bvWncFx'  # production trial

        subscription_response = stripe.Subscription.create(
            customer=customer_response.id,
            collection_method="send_invoice",
            days_until_due=14,
            cancel_at_period_end=True,
            items=[
                {
                    "plan": plan,  # trial plan
                },
            ],
            trial_end=timestamp,
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

        user = User.objects.get(pk=instance.pk)

        clients = Group.objects.get(name='clients')
        user.groups.add(clients)

        total = Total(user=user, total='All')
        total.save()

    else:
        None


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
