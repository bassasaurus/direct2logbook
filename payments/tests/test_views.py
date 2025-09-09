from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from unittest.mock import patch
from django.contrib.messages import get_messages
from profile.models import Profile
from datetime import date, timedelta
from types import SimpleNamespace


class PaymentViewsTest(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Group
        # Ensure 'clients' group exists
        Group.objects.get_or_create(name='clients')
        self.user = User.objects.create_user(
            username='testuser', email='testuser@example.com', password='testpass')
        self.client.login(username='testuser', password='testpass')
        # Ensure the user has a Profile (signals may be disabled/mocked in tests)
        Profile.objects.update_or_create(
            user=self.user,
            defaults={
                "end_date": date.today() + timedelta(days=14),
                "subscription_id": "sub_test_123",
            },
        )

    @patch("payments.views.stripe.Subscription.retrieve")
    def test_success_view(self, mock_retrieve):
        # Return a minimal object with the attributes the view expects
        mock_retrieve.return_value = SimpleNamespace(
            trial_end=1700000000,  # arbitrary timestamp
            current_period_end=1700000000,
            plan=SimpleNamespace(nickname="Trial"),
        )
        response = self.client.get(
            reverse('payment_success', args=[self.user.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment Successful")

    def test_canceled_view(self):
        response = self.client.get(f'/payments/canceled/{self.user.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment Canceled")

    # @patch("payments.views.stripe.Customer.modify")
    # def test_subscription_cancel_view_success(self, mock_modify):
    #     mock_modify.return_value = {
    #         "id": "cus_test", "cancel_at_period_end": True}
    #     response = self.client.get(
    #         "/payments/subscription_canceled/", follow=True)
    #     self.assertEqual(response.status_code, 200)
    #     messages = [m.message for m in get_messages(response.wsgi_request)]
    #     self.assertIn(
    #         "Your subscription will be canceled at the end of the billing period.", messages)

    # @patch("payments.views.stripe.Customer.modify")
    # def test_subscription_cancel_view_failure(self, mock_modify):
    #     mock_modify.side_effect = Exception("Stripe error")
    #     response = self.client.get(
    #         "/payments/subscription_canceled/", follow=True)
    #     self.assertEqual(response.status_code, 200)
    #     messages = [m.message for m in get_messages(response.wsgi_request)]
    #     self.assertIn(
    #         "There was an error cancelling your subscription. Please try again.", messages)
