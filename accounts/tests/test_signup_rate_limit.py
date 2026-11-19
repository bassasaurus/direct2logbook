from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(
    DEBUG=False,
    SECURE_SSL_REDIRECT=False,
    ALLAUTH_TRUSTED_PROXY_COUNT=1,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                        'LOCATION': 'signup-rate-limit-tests'}},
)
class SignupRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.url = reverse('account_signup')

    def post(self, data=None, ip='198.51.100.10'):
        # New sessions must share the IP's limit, just as separate browsers do.
        return Client().post(self.url, data or {'email': 'invalid'},
                             REMOTE_ADDR='127.0.0.1', HTTP_X_FORWARDED_FOR=ip)

    @patch('django_recaptcha.fields.ReCaptchaField.clean', return_value='valid-test-token')
    def test_sixth_signup_is_blocked_before_creating_user_or_sending_email(self, captcha):
        initial = get_user_model().objects.count()
        for index in range(5):
            email = f'signup-limit-{index}@example.com'
            response = self.post({'email': email, 'email2': email,
                                  'first_name': 'Signup', 'last_name': 'Test',
                                  'password1': 'LongSignupPassword972!',
                                  'password2': 'LongSignupPassword972!',
                                  'g-recaptcha-response': 'valid-test-token'})
            form = response.context.get('form') if response.context else None
            self.assertEqual(response.status_code, 302, form.errors if form is not None else response.content)
            self.assertTrue(get_user_model().objects.filter(email=email).exists())
        self.assertEqual(get_user_model().objects.count(), initial + 5)
        before_emails = len(mail.outbox)
        response = self.post({'email': 'blocked-signup@example.com', 'email2': 'blocked-signup@example.com',
                              'first_name': 'Blocked', 'last_name': 'Test',
                              'password1': 'LongSignupPassword972!', 'password2': 'LongSignupPassword972!',
                              'g-recaptcha-response': 'valid-test-token'})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(get_user_model().objects.count(), initial + 5)
        self.assertFalse(get_user_model().objects.filter(email='blocked-signup@example.com').exists())
        self.assertEqual(len(mail.outbox), before_emails)
        self.assertEqual(captcha.call_count, 5)

    def test_invalid_attempts_count_but_other_ips_and_get_requests_are_allowed(self):
        for _ in range(5):
            self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.post().status_code, 429)
        self.assertEqual(self.post(ip='198.51.100.11').status_code, 200)
        self.assertEqual(Client().get(self.url, REMOTE_ADDR='127.0.0.1',
                                     HTTP_X_FORWARDED_FOR='198.51.100.10').status_code, 200)

    @patch('allauth.core.internal.ratelimit.time.time')
    def test_signup_is_allowed_again_after_an_hour(self, now):
        now.return_value = 1800000000
        for _ in range(5):
            self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.post().status_code, 429)
        now.return_value += 3601
        self.assertEqual(self.post().status_code, 200)
