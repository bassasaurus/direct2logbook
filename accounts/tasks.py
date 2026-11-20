from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string

from accounts.social_providers import SOCIAL_PROVIDER_NAMES

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount


@shared_task(ignore_result=True, max_retries=0)
def send_google_welcome(user_id, home_url, provider='google'):
    # Retain the existing Celery task name for already queued Google messages.
    if provider not in SOCIAL_PROVIDER_NAMES:
        return
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None or not EmailAddress.objects.filter(
        user=user, email=user.email, verified=True,
    ).exists():
        return
    body = render_to_string('account/email/google_welcome.txt', {
        'first_name': user.first_name, 'home_url': home_url,
        'provider_name': SOCIAL_PROVIDER_NAMES[provider],
    })
    sent = send_mail('Welcome to Direct2Logbook', body, settings.DEFAULT_FROM_EMAIL,
                     [user.email], fail_silently=False)
    if sent != 1:
        raise RuntimeError('Mail backend did not submit social sign-in welcome email')


@shared_task(ignore_result=True, max_retries=0)
def send_google_connected(user_id, account_id, connections_url):
    account = SocialAccount.objects.select_related('user').filter(
        pk=account_id, user_id=user_id, provider__in=SOCIAL_PROVIDER_NAMES, user__is_active=True,
    ).first()
    if account is None:
        return
    user = account.user
    body = render_to_string('account/email/google_connected.txt', {
        'first_name': user.first_name, 'connections_url': connections_url,
        'provider_name': SOCIAL_PROVIDER_NAMES[account.provider],
    })
    sent = send_mail(f'{SOCIAL_PROVIDER_NAMES[account.provider]} sign-in linked to your Direct2Logbook account', body,
                    settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    if sent != 1:
        raise RuntimeError('Mail backend did not submit social sign-in connection email')


@shared_task(bind=True, ignore_result=True, max_retries=6)
def cleanup_deleted_account(self, cleanup_id, using='default'):
    from .deletion import clean_external_resources
    try:
        clean_external_resources(cleanup_id, using)
    except Exception as error:
        raise self.retry(exc=RuntimeError(type(error).__name__), countdown=300)
