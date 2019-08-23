from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from accounts.models import Profile
import stripe
from decouple import config

@receiver(post_save, sender=User)
def create_customer(sender, instance, created, **kwargs):
    name = '{} {}'.format(instance.first_name, instance.last_name )

    user = instance.pk

    profile = Profile.objects.get(user=user)

    stripe.api_key = config('STRIPE_TEST_SECRET_KEY')

    response = stripe.Customer.create(
        description="New Customer",
        name=name,
        email=instance.email
    )

    customer_id = response.id
    print(customer_id)
    profile.customer_id = customer_id
    profile.save()
