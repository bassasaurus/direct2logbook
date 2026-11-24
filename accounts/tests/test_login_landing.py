from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from allauth.account.models import EmailAddress
from profile.models import Profile


@override_settings(SECURE_SSL_REDIRECT=False, ACCOUNT_RATE_LIMITS=False)
class LoginLandingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='landing', email='landing@example.com', password='Login-test-527!')
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True, primary=True)

    def login_with_access(self, expected, **flags):
        Profile.objects.filter(user=self.user).update(**(dict(active=False, trial=False, expired=False, free_access=False) | flags))
        response = self.client.post(reverse('account_login') + '?next=/flights/logbook/', {
            'login': self.user.email, 'password': 'Login-test-527!', 'next': '/flights/logbook/',
        })
        self.assertRedirects(response, reverse(expected), fetch_redirect_response=False)

    def test_active_subscription_ignores_previous_page(self):
        self.login_with_access('home', active=True)

    def test_trial_lands_on_home(self):
        self.login_with_access('home', trial=True)

    def test_free_access_lands_on_home(self):
        self.login_with_access('home', free_access=True)

    def test_lapsed_subscription_lands_on_profile(self):
        self.login_with_access('profile', active=True, expired=True)

    def test_no_access_lands_on_profile(self):
        self.login_with_access('profile')

    def test_wrong_password_does_not_redirect(self):
        response = self.client.post(reverse('account_login'), {'login': self.user.email, 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_welcome_back_message_stays_visible_on_home(self):
        self.login_with_access('home', active=True)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Welcome back')
        from html.parser import HTMLParser
        class Alerts(HTMLParser):
            def __init__(self):
                super().__init__()
                self.alerts = []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if attrs.get('role') == 'alert':
                    self.alerts.append(attrs)
        parser = Alerts()
        parser.feed(response.content.decode())
        success = [attrs for attrs in parser.alerts if attrs.get('class') == 'text-success']
        self.assertTrue(success)
        self.assertNotIn('data-animate', success[0])
