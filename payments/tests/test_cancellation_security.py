import re
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class SubscriptionCancellationSecurityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='cancel_owner')
        self.other = get_user_model().objects.create_user(username='cancel_other')
        for user, subscription in (
            (self.user, 'sub_owner'), (self.other, 'sub_other'),
        ):
            profile = user.profile
            profile.customer_id = 'cus_' + user.username
            profile.subscription_id = subscription
            profile.active = True
            profile.monthly = True
            profile.end_date = date.today() + timedelta(days=14)
            profile.save()
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.url = reverse('subscription_canceled')
        patcher = patch('payments.views.stripe.Subscription.modify')
        self.modify = patcher.start()
        self.addCleanup(patcher.stop)
        self.modify.return_value = SimpleNamespace(current_period_end=1893456000)

    def csrf_token(self):
        # Read the actual rendered form; this also supports CSRF_USE_SESSIONS.
        with patch('profile.views.stripe.checkout.Session.create',
                   return_value=SimpleNamespace(id='cs_test')):
            response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        match = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            response.content.decode(),
        )
        self.assertIsNotNone(match, 'Profile cancellation form needs a CSRF token')
        return match.group(1)

    def assert_not_canceled(self):
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.canceled)
        self.assertTrue(self.user.profile.active)
        self.modify.assert_not_called()

    def test_anonymous_get_requires_login(self):
        response = Client().get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login', response.url)
        self.assert_not_canceled()

    def test_anonymous_post_requires_login(self):
        response = Client().post(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login', response.url)
        self.assert_not_canceled()

    def test_authenticated_get_cannot_cancel(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)
        self.assert_not_canceled()

    def test_post_without_csrf_token_cannot_cancel(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        self.assert_not_canceled()

    def test_post_with_invalid_csrf_token_cannot_cancel(self):
        self.csrf_token()
        response = self.client.post(self.url, {'csrfmiddlewaretoken': 'invalid'})

        self.assertEqual(response.status_code, 403)
        self.assert_not_canceled()

    def test_valid_post_cancels_only_authenticated_users_subscription(self):
        token = self.csrf_token()
        response = self.client.post(self.url, {
            'csrfmiddlewaretoken': token,
            'user': self.other.pk, 'subscription_id': 'sub_other',
        })

        self.assertEqual(response.status_code, 200)
        self.modify.assert_called_once_with('sub_owner', cancel_at_period_end=True)
        self.user.profile.refresh_from_db()
        self.other.profile.refresh_from_db()
        self.assertTrue(self.user.profile.canceled)
        self.assertFalse(self.other.profile.canceled)
        self.assertTrue(self.other.profile.active)

    def test_missing_subscription_does_not_contact_stripe(self):
        token = self.csrf_token()
        profile = self.user.profile
        profile.subscription_id = ''
        profile.save(update_fields=['subscription_id'])

        response = self.client.post(self.url, {'csrfmiddlewaretoken': token})

        self.assertEqual(response.status_code, 400)
        self.assert_not_canceled()
