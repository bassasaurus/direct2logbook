from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from allauth.account.models import EmailAddress
from allauth.account.signals import user_signed_up
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialLogin
from allauth.socialaccount.signals import social_account_added
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.forms import SocialProviderSignupForm
from accounts.tasks import send_google_connected, send_google_welcome
from payments.models import BillingProvisioning


@override_settings(SECURE_SSL_REDIRECT=False,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AdditionalSocialProviderTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.apps = {}
        for provider in ('apple', 'facebook'):
            app = SocialApp.objects.create(provider=provider, name=provider.title(),
                                           client_id=f'{provider}-client', secret='test-key-id', key='test-team-id')
            app.sites.add(Site.objects.get_current())
            self.apps[provider] = app

    def test_signin_and_signup_show_only_configured_providers(self):
        for page in ('account_login', 'account_signup'):
            response = self.client.get(reverse(page))
            self.assertContains(response, 'Sign in with Apple')
            self.assertContains(response, 'Continue with Facebook')
            self.assertContains(response, reverse('apple_login'))
            self.assertContains(response, reverse('facebook_login'))
            self.assertContains(response, 'method="post"')
        self.apps['apple'].delete()
        self.assertNotContains(self.client.get(reverse('account_login')), 'Sign in with Apple')
        self.apps['facebook'].delete()
        self.assertNotContains(self.client.get(reverse('account_signup')), 'Continue with Facebook')

    def test_provider_start_requires_post_and_csrf_and_preserves_next(self):
        for provider in self.apps:
            with self.subTest(provider=provider):
                url = reverse(f'{provider}_login')
                self.assertEqual(self.client.get(url).status_code, 200)
                self.assertEqual(Client(enforce_csrf_checks=True).post(url).status_code, 403)
                response = self.client.post(url + '?next=/profile/')
                self.assertEqual(response.status_code, 302)
                params = parse_qs(urlsplit(response.url).query)
                self.assertEqual(params['client_id'], [f'{provider}-client'])
                self.assertIn('state', params)
                self.assertIn(reverse(f'{provider}_callback'), params['redirect_uri'][0])

    def login(self, provider, email='provider@example.com'):
        user = get_user_model()(email=email, first_name='Steve', last_name='Rogers')
        account = SocialAccount(provider=provider, uid=f'{provider}-user')
        return SocialLogin(user=user, account=account)

    def test_provider_email_cannot_be_spoofed_in_signup_form(self):
        for provider in self.apps:
            form = SocialProviderSignupForm(sociallogin=self.login(provider), data={
                'first_name': 'Steve', 'last_name': 'Rogers', 'email': 'spoof@example.com', 'email2': 'spoof@example.com'})
            self.assertTrue(form.fields['email'].disabled)
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data['email'], 'provider@example.com')

    def test_provider_without_email_can_collect_one_for_normal_verification(self):
        form = SocialProviderSignupForm(sociallogin=self.login('facebook', email=''), data={
            'first_name': 'Steve', 'last_name': 'Rogers', 'email': 'chosen@example.com', 'email2': 'chosen@example.com'})
        self.assertFalse(form.fields['email'].disabled)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['email'], 'chosen@example.com')

    @patch('payments.signals.provision_trial_task.apply_async')
    @patch('accounts.signals.send_google_welcome.apply_async')
    def test_only_verified_provider_signup_queues_trial_and_welcome_after_commit(self, welcome, trial):
        for provider in self.apps:
            for verified in (False, True):
                with self.subTest(provider=provider, verified=verified):
                    welcome.reset_mock()
                    trial.reset_mock()
                    user = get_user_model().objects.create_user(username=f'{provider}-{verified}', email=f'{provider}-{verified}@example.com')
                    EmailAddress.objects.create(user=user, email=user.email, verified=verified)
                    request = SimpleNamespace(build_absolute_uri=lambda path: 'http://testserver' + path)
                    login = SimpleNamespace(account=SimpleNamespace(provider=provider))
                    with self.captureOnCommitCallbacks(execute=True):
                        user_signed_up.send(sender=type(user), request=request, user=user, sociallogin=login)
                        trial.assert_not_called()
                        welcome.assert_not_called()
                    if verified:
                        trial.assert_called_once_with(args=(user.pk,), retry=False)
                        welcome.assert_called_once_with(args=(user.pk, 'http://testserver/home/', provider), retry=False)
                    else:
                        trial.assert_not_called()
                        welcome.assert_not_called()
                        self.assertFalse(BillingProvisioning.objects.filter(user=user).exists())

    @patch('accounts.signals.send_google_connected.apply_async')
    def test_linking_notifies_existing_account_without_starting_another_trial(self, publish):
        user = get_user_model().objects.create_user(username='link-owner', email='owner@example.com')
        request = SimpleNamespace(build_absolute_uri=lambda path: 'http://testserver' + path)
        for provider in self.apps:
            publish.reset_mock()
            account = SocialAccount.objects.create(user=user, provider=provider, uid='linked')
            with self.captureOnCommitCallbacks(execute=True):
                social_account_added.send(sender=type(account), request=request, sociallogin=SimpleNamespace(account=account))
                publish.assert_not_called()
            publish.assert_called_once_with(args=(user.pk, account.pk, 'http://testserver' + reverse('socialaccount_connections')), retry=False)
            self.assertFalse(BillingProvisioning.objects.filter(user=user).exists())
            send_google_connected.run(user.pk, account.pk, 'http://testserver/accounts/3rdparty/')
            self.assertEqual(mail.outbox[-1].to, [user.email])
            self.assertIn(provider.title() + ' sign-in', mail.outbox[-1].subject)

    def test_welcome_uses_correct_provider_name(self):
        user = get_user_model().objects.create_user(username='welcome-owner', email='owner@example.com')
        EmailAddress.objects.create(user=user, email=user.email, verified=True)
        for provider in self.apps:
            send_google_welcome.run(user.pk, 'http://testserver/home/', provider)
            self.assertIn(f'using {provider.title()}', mail.outbox[-1].body)
            self.assertNotIn('using Google', mail.outbox[-1].body)
