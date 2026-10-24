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
    """
    Create the local account records when a user is created.
    External billing operations are intentionally excluded.
    """

    if not created:
        return

    # Create the user's profile.
    Profile.objects.get_or_create(user=instance)

    # Assign the user to the clients group if it exists.
    clients = Group.objects.filter(name='clients').first()

    if clients:
        instance.groups.add(clients)

    # Initialize the user's flight totals.

    Total.objects.get_or_create(
        user=instance,
        total='All',
    )


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
