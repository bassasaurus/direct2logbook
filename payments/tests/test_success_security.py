from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class PaymentSuccessSecurityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='success_owner')
        self.other = get_user_model().objects.create_user(username='success_other')
        for user, subscription in ((self.user, 'sub_owner'), (self.other, 'sub_other')):
            profile = user.profile
            profile.subscription_id = subscription
            profile.save(update_fields=['subscription_id'])
        self.client.force_login(self.user)
        self.url = reverse('payment_success', args=[self.user.pk])
        patcher = patch('payments.views.stripe.Subscription.retrieve')
        self.retrieve = patcher.start()
        self.addCleanup(patcher.stop)
        self.retrieve.return_value = SimpleNamespace(
            current_period_end=1893456000,
            plan=SimpleNamespace(nickname='Owner plan'),
        )

    def test_owner_can_view_own_subscription(self):
        response = self.client.get(self.url)

        self.assertContains(response, 'Payment Successful')
        self.assertContains(response, 'Owner plan')
        self.retrieve.assert_called_once_with('sub_owner')

    def test_other_users_subscription_cannot_be_viewed(self):
        response = self.client.get(reverse('payment_success', args=[self.other.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, 'Owner plan', status_code=404)
        self.retrieve.assert_not_called()

    def test_anonymous_request_requires_login_before_stripe(self):
        self.client.logout()
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login', response.url)
        self.retrieve.assert_not_called()

    def test_unknown_user_id_is_rejected_before_stripe(self):
        response = self.client.get(reverse('payment_success', args=[self.other.pk + 1000]))

        self.assertEqual(response.status_code, 404)
        self.retrieve.assert_not_called()

    def test_unprovisioned_user_does_not_contact_stripe(self):
        profile = self.user.profile
        profile.subscription_id = ''
        profile.save(update_fields=['subscription_id'])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)
        self.retrieve.assert_not_called()

    def test_missing_profile_does_not_contact_stripe(self):
        self.user.profile.delete()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)
        self.retrieve.assert_not_called()
