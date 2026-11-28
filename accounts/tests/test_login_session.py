from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from profile.models import Profile


@override_settings(SECURE_SSL_REDIRECT=False, ACCOUNT_RATE_LIMITS=False)
class LoginSessionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('mobile-login', email='mobile@example.com', password='Test-login-782!')
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True, primary=True)
        Profile.objects.filter(user=self.user).update(free_access=True, active=False, expired=True, trial=False)
        self.user.refresh_from_db()
        self.client = Client(enforce_csrf_checks=True)

    def token(self):
        response = self.client.get(reverse('login_session_token'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertNotIn('Access-Control-Allow-Origin', response)
        return response.json()['csrf_token']

    def sign_in(self, token, **extra):
        return self.client.post(reverse('account_login'), {
            'login': self.user.email, 'password': 'Test-login-782!',
            'csrfmiddlewaretoken': token, 'next': reverse('profile'),
        }, **extra)

    def test_expired_session_rejects_old_token_and_fresh_token_allows_home(self):
        stale = self.token()
        self.client.session.flush()
        rejected = self.sign_in(stale)
        self.assertEqual(rejected.status_code, 403)
        self.assertContains(rejected, 'Return to Sign In', status_code=403)
        self.assertNotContains(rejected, 'Test-login-782!', status_code=403)
        self.assertNotIn('_auth_user_id', self.client.session)
        response = self.sign_in(self.token())
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)
        self.assertEqual(self.client.get(reverse('flight_list')).status_code, 200)

    def test_valid_token_does_not_bypass_cross_origin_protection(self):
        response = self.sign_in(self.token(), HTTP_ORIGIN='https://untrusted.example')
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_refresh_endpoint_does_not_accept_post_or_log_in(self):
        response = self.client.post(reverse('login_session_token'))
        self.assertIn(response.status_code, (403, 405))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_includes_same_origin_refresh_script(self):
        response = self.client.get(reverse('account_login'))
        self.assertContains(response, 'data-session-token-url="'+reverse('login_session_token')+'"')
        self.assertContains(response, 'js/login_session.js')
        self.assertIn('no-store', response['Cache-Control'])

    def test_ajax_csrf_failure_is_friendly_and_still_rejected(self):
        response = self.client.post(reverse('user_update', args=[self.user.pk]), {}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['message'], 'This form has expired. Refresh the page and try again.')

    def test_free_access_home_does_not_bounce_to_profile(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)
        self.assertEqual(self.client.get(reverse('flight_list')).status_code, 200)

    def test_lapsed_account_still_returns_to_profile(self):
        Profile.objects.filter(user=self.user).update(free_access=False, active=True, expired=True)
        response = self.sign_in(self.token())
        self.assertRedirects(response, reverse('profile'), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse('home')), reverse('profile'), fetch_redirect_response=False)
