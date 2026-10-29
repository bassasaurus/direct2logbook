from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialLogin
from allauth.socialaccount.providers.google.provider import GoogleProvider
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class GoogleSigninTests(TestCase):
    def setUp(self):
        cache.clear()
        welcome = patch('accounts.signals.send_google_welcome.apply_async')
        self.welcome = welcome.start()
        self.addCleanup(welcome.stop)
        connected = patch('accounts.signals.send_google_connected.apply_async')
        self.connected = connected.start()
        self.addCleanup(connected.stop)
        self.app = SocialApp.objects.create(provider='google', name='Google',
                                            client_id='test-client', secret='test-secret')
        self.app.sites.add(Site.objects.get_current())

    def start(self, process='login'):
        response = self.client.post(reverse('google_login') + '?process=' + process)
        self.assertEqual(response.status_code, 302)
        params = parse_qs(urlsplit(response.url).query)
        self.assertIn('code_challenge', params)
        return params['state'][0]

    def callback(self, email='google@example.com', verified=True, uid='google-user', complete_signup=True, process='login'):
        state = self.start(process)
        user = get_user_model()(email=email, first_name='Google', last_name='Tester')
        login = SocialLogin(user=user, account=SocialAccount(provider='google', uid=uid),
                            provider=GoogleProvider(request=None, app=self.app),
                            email_addresses=[EmailAddress(email=email, verified=verified, primary=True)])
        with patch('allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter.get_access_token_data',
                   return_value={'access_token': 'fake-token'}), patch(
                'allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter.complete_login',
                return_value=login):
            response = self.client.get(reverse('google_callback'), {'state': state, 'code': 'fake-code'})
        if complete_signup and response.status_code == 302 and response.url == reverse('socialaccount_signup'):
            response = self.client.post(reverse('socialaccount_signup'), {
                'first_name': 'Steve', 'last_name': 'Rogers', 'email': email, 'email2': email,
            })
        return response

    def test_button_is_available_only_when_configured(self):
        for page in ('account_login', 'account_signup'):
            with self.subTest(page=page):
                response = self.client.get(reverse(page), {'next': '/flights/logbook/'})
                self.assertContains(response, 'Sign in with Google')
                self.assertContains(response, 'next=%2Fflights%2Flogbook%2F')
        self.app.delete()
        for page in ('account_login', 'account_signup'):
            with self.subTest(page=page):
                self.assertNotContains(self.client.get(reverse(page)), 'Sign in with Google')

    def test_login_requires_csrf_and_get_does_not_start_oauth(self):
        response = self.client.get(reverse('google_login'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Client(enforce_csrf_checks=True).post(reverse('google_login')).status_code, 403)

    @patch('payments.signals.provision_trial_task.apply_async')
    def test_verified_signup_logs_in_and_queues_trial_after_commit(self, publish):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.callback()
            publish.assert_not_called()
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(email='google@example.com')
        self.assertEqual(user.username, 'srogers')
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.assertTrue(EmailAddress.objects.get(user=user).verified)
        publish.assert_called_once_with(args=(user.pk,), retry=False)
        self.welcome.assert_called_once_with(
            args=(user.pk, 'http://testserver/home/'), retry=False,
        )
        self.connected.assert_not_called()

    def test_new_google_user_reviews_signup_before_account_creation(self):
        response = self.callback(complete_signup=False)
        self.assertRedirects(response, reverse('socialaccount_signup'))
        self.assertFalse(get_user_model().objects.filter(email='google@example.com').exists())
        page = self.client.get(reverse('socialaccount_signup'))
        self.assertContains(page, 'First Name')
        self.assertContains(page, 'Last Name')

    @patch('payments.signals.provision_trial_task.apply_async')
    def test_username_collision_generates_unique_name(self, publish):
        get_user_model().objects.create_user(username='srogers', email='existing@example.com')
        self.callback()
        user = get_user_model().objects.get(email='google@example.com')
        self.assertTrue(user.username.startswith('srogers'))
        self.assertNotEqual(user.username, 'srogers')

    @patch('payments.signals.provision_trial_task.apply_async')
    def test_unverified_signup_waits_for_email_confirmation(self, publish):
        with self.captureOnCommitCallbacks(execute=True):
            self.callback(verified=False)
        self.assertNotIn('_auth_user_id', self.client.session)
        publish.assert_not_called()
        self.welcome.assert_not_called()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['google@example.com'])

    @patch('payments.signals.provision_trial_task.apply_async')
    def test_signup_cannot_replace_google_email(self, publish):
        self.callback(complete_signup=False)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('socialaccount_signup'), {
                'first_name': 'Steve', 'last_name': 'Rogers',
                'email': 'changed@example.com', 'email2': 'changed@example.com',
            })
        self.assertFalse(EmailAddress.objects.filter(email='changed@example.com').exists())
        user = get_user_model().objects.get(email='google@example.com')
        self.assertTrue(EmailAddress.objects.get(user=user).verified)
        publish.assert_called_once_with(args=(user.pk,), retry=False)

    @patch('payments.signals.provision_trial_task.apply_async')
    def test_matching_email_does_not_link_existing_account(self, publish):
        user = get_user_model().objects.create_user(username='existing', email='google@example.com')
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        with self.captureOnCommitCallbacks(execute=True):
            self.callback()
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertFalse(SocialAccount.objects.filter(user=user).exists())
        publish.assert_not_called()

    @patch('payments.signals.provision_trial_task.apply_async')
    def test_returning_google_user_does_not_get_another_trial(self, publish):
        user = get_user_model().objects.create_user(username='returning', email='google@example.com')
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        SocialAccount.objects.create(user=user, provider='google', uid='google-user')
        with self.captureOnCommitCallbacks(execute=True):
            self.callback()
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        publish.assert_not_called()
        self.welcome.assert_not_called()
        self.connected.assert_not_called()

    @patch('payments.signals.provision_trial_task.apply_async')
    def test_linking_google_to_existing_account_queues_connection_email_only(self, publish):
        user = get_user_model().objects.create_user(username='existing_google', email='google@example.com')
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        self.client.force_login(user)
        with self.captureOnCommitCallbacks(execute=True):
            self.callback(process='connect')
            self.connected.assert_not_called()
        account = SocialAccount.objects.get(user=user, provider='google')
        self.connected.assert_called_once_with(
            args=(user.pk, account.pk, 'http://testserver' + reverse('socialaccount_connections')), retry=False,
        )
        self.welcome.assert_not_called()
        publish.assert_not_called()

    @patch('payments.signals.provision_trial_task.apply_async')
    def test_inactive_google_user_cannot_login(self, publish):
        user = get_user_model().objects.create_user(username='inactive', email='google@example.com', is_active=False)
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        SocialAccount.objects.create(user=user, provider='google', uid='google-user')
        with self.captureOnCommitCallbacks(execute=True):
            self.callback()
        self.assertNotIn('_auth_user_id', self.client.session)
        publish.assert_not_called()

    @patch('allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter.get_access_token_data')
    def test_invalid_state_does_not_exchange_code(self, exchange):
        self.client.get(reverse('google_callback'), {'state': 'invalid', 'code': 'fake-code'})
        exchange.assert_not_called()
        self.assertNotIn('_auth_user_id', self.client.session)
