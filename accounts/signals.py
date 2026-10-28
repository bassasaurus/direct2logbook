import logging
from functools import partial

from allauth.account.models import EmailAddress
from allauth.account.signals import user_signed_up
from allauth.socialaccount.signals import social_account_added
from django.db import transaction
from django.dispatch import receiver
from django.urls import reverse
from kombu.exceptions import OperationalError

from .tasks import send_google_welcome, send_google_connected

logger = logging.getLogger(__name__)


def publish_google_welcome(user_id, home_url):
    try:
        send_google_welcome.apply_async(args=(user_id, home_url), retry=False)
    except OperationalError:
        logger.exception('Could not queue Google welcome email for user_id=%s', user_id)


@receiver(user_signed_up, dispatch_uid='accounts.google_signup_welcome')
def google_signup_welcome(sender, request, user, sociallogin=None, **kwargs):
    if sociallogin is None or sociallogin.account.provider != 'google':
        return
    if not EmailAddress.objects.filter(user=user, email=user.email, verified=True).exists():
        return
    transaction.on_commit(
        partial(publish_google_welcome, user.pk, request.build_absolute_uri(reverse('home'))),
        using=user._state.db,
    )


def publish_google_connected(user_id, account_id, connections_url):
    try:
        send_google_connected.apply_async(args=(user_id, account_id, connections_url), retry=False)
    except OperationalError:
        logger.exception('Could not queue Google connection email for user_id=%s', user_id)


@receiver(social_account_added, dispatch_uid='accounts.google_connected_email')
def google_connected_email(sender, request, sociallogin, **kwargs):
    account = sociallogin.account
    if account.provider != 'google':
        return
    transaction.on_commit(
        partial(publish_google_connected, account.user_id, account.pk,
                request.build_absolute_uri(reverse('socialaccount_connections'))),
        using=account._state.db,
    )
