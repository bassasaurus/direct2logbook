from django.test import SimpleTestCase
from django.urls import reverse, resolve
from payments.views import (
    stripe_webhook_view,
    success_view,
    subscription_cancel_view,
    canceled_view,
)


class TestPaymentsURLs(SimpleTestCase):

    def test_stripe_webhook_url_resolves(self):
        url = reverse('stripe_webhook')
        self.assertEqual(resolve(url).func, stripe_webhook_view)

    def test_payment_success_url_resolves(self):
        url = reverse('payment_success', kwargs={'user': 1})
        self.assertEqual(resolve(url).func, success_view)

    def test_payment_canceled_url_resolves(self):
        url = reverse('payment_canceled', kwargs={'user': 1})
        self.assertEqual(resolve(url).func, canceled_view)

    def test_subscription_canceled_url_resolves(self):
        url = reverse('subscription_canceled')
        self.assertEqual(resolve(url).func, subscription_cancel_view)
