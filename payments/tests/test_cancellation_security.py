import re
from datetime import date, timedelta, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import stripe
from django.conf import settings

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
        self.subscription = {
            'id': 'sub_owner', 'customer': 'cus_cancel_owner', 'status': 'active',
            'current_period_end': 1893456000, 'cancel_at_period_end': False,
            'items': {'data': [{'price': {'recurring': {'interval': 'month'}}}]},
        }
        self.modify.return_value = {**self.subscription, 'cancel_at_period_end': True}
        retrieve_patch = patch('payments.views.stripe.Subscription.retrieve', return_value=self.subscription)
        self.retrieve = retrieve_patch.start()
        self.addCleanup(retrieve_patch.stop)

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
        self.modify.assert_called_once_with('sub_owner', cancel_at_period_end=True, api_key=settings.STRIPE_SECRET_KEY)
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

    def test_scheduled_cancellation_retains_paid_access_and_updates_period(self):
        token = self.csrf_token()
        response = self.client.post(self.url, {'csrfmiddlewaretoken': token})
        self.assertContains(response, 'Cancellation scheduled')
        profile = self.user.profile
        profile.refresh_from_db()
        self.assertTrue(profile.active)
        self.assertFalse(profile.expired)
        self.assertTrue(profile.monthly)
        self.assertEqual(profile.end_date, datetime.fromtimestamp(1893456000, tz=timezone.utc).date())
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)
        from api.mobile_profile import snapshot
        self.assertEqual(snapshot(self.user)['subscription']['status'], 'Cancellation scheduled')

    def test_modify_failure_preserves_local_access_and_shows_retry_message(self):
        token = self.csrf_token()
        self.modify.side_effect = stripe.error.APIConnectionError('unavailable')
        with self.assertLogs('django.payments.webhooks', level='ERROR'):
            response = self.client.post(self.url, {'csrfmiddlewaretoken': token})
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, 'We couldn’t confirm your cancellation.', status_code=503)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.active)
        self.assertFalse(self.user.profile.canceled)

    def test_wrong_stripe_customer_is_rejected_before_modification(self):
        token = self.csrf_token()
        self.retrieve.return_value = {**self.subscription, 'customer': 'cus_other'}
        with self.assertLogs('django.payments.webhooks', level='ERROR'):
            response = self.client.post(self.url, {'csrfmiddlewaretoken': token})
        self.assertEqual(response.status_code, 503)
        self.modify.assert_not_called()
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.canceled)

    def test_ended_subscription_is_not_reactivated(self):
        token = self.csrf_token()
        self.modify.return_value = {**self.subscription, 'status': 'canceled', 'cancel_at_period_end': False}
        response = self.client.post(self.url, {'csrfmiddlewaretoken': token})
        self.assertContains(response, 'Your subscription has ended')
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.active)
        self.assertTrue(self.user.profile.expired)

    def test_last_billing_day_remains_accessible_until_stripe_ends_it(self):
        token = self.csrf_token()
        today = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59)
        self.modify.return_value = {**self.subscription, 'cancel_at_period_end': True, 'current_period_end': int(today.timestamp())}
        self.client.post(self.url, {'csrfmiddlewaretoken': token})
        with patch('profile.views.stripe.checkout.Session.create', return_value=SimpleNamespace(id='cs_test')):
            response = self.client.get(reverse('profile'))
        self.assertFalse(response.context['passed_end_date'])
        self.assertContains(response, 'Cancellation scheduled')
        self.assertNotContains(response, 'Your subscription is canceled')
        from api.mobile_profile import snapshot
        self.assertEqual(snapshot(self.user)['subscription']['status'], 'Cancellation scheduled')

    def test_unconfirmed_stripe_response_does_not_mark_local_cancellation(self):
        token = self.csrf_token()
        self.modify.return_value = self.subscription
        with self.assertLogs('django.payments.webhooks', level='ERROR'):
            response = self.client.post(self.url, {'csrfmiddlewaretoken': token})
        self.assertEqual(response.status_code, 503)
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.canceled)
        self.assertTrue(self.user.profile.active)

    def test_past_due_cancellation_does_not_grant_paid_access(self):
        token = self.csrf_token()
        self.modify.return_value = {**self.subscription, 'status': 'past_due', 'cancel_at_period_end': True}
        response = self.client.post(self.url, {'csrfmiddlewaretoken': token})
        self.assertContains(response, 'Cancellation scheduled')
        self.assertNotContains(response, 'Your access continues')
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.active)
        self.assertTrue(self.user.profile.expired)

    def test_already_ended_subscription_is_a_safe_noop(self):
        token = self.csrf_token()
        self.retrieve.return_value = {**self.subscription, 'status': 'canceled', 'cancel_at_period_end': False}
        response = self.client.post(self.url, {'csrfmiddlewaretoken': token})
        self.assertContains(response, 'Your subscription has ended')
        self.modify.assert_not_called()
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.active)
        self.assertTrue(self.user.profile.expired)
