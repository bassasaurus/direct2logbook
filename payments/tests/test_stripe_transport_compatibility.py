"""Exercise real SDK serialization without contacting Stripe."""
import json
from unittest.mock import Mock, patch
from urllib.parse import parse_qs

import stripe
from django.test import SimpleTestCase


class StripeTransportCompatibilityTests(SimpleTestCase):
    def setUp(self):
        self.client = Mock(spec=stripe.http_client.HTTPClient)
        self.client.name = 'synthetic-test-client'
        self.key = patch.object(stripe, 'api_key', 'sk_test_synthetic')
        self.transport = patch.object(stripe, 'default_http_client', self.client)
        self.key.start()
        self.transport.start()
        self.addCleanup(self.key.stop)
        self.addCleanup(self.transport.stop)

    def test_customer_request_preserves_idempotency_and_account_api_version(self):
        self.client.request_with_retries.return_value = (json.dumps({'id': 'cus_test', 'object': 'customer'}), 200, {})
        customer = stripe.Customer.create(email='synthetic@example.com', idempotency_key='customer-test-key')
        self.assertEqual(customer.id, 'cus_test')
        args, kwargs = self.client.request_with_retries.call_args
        self.assertEqual(args[:2], ('post', 'https://api.stripe.com/v1/customers'))
        self.assertEqual(args[2]['Idempotency-Key'], 'customer-test-key')
        self.assertNotIn('Stripe-Version', args[2])
        self.assertEqual(parse_qs(args[3])['email'], ['synthetic@example.com'])

    def test_subscription_request_preserves_trial_parameters(self):
        self.client.request_with_retries.return_value = (json.dumps({'id': 'sub_test', 'object': 'subscription'}), 200, {})
        subscription = stripe.Subscription.create(customer='cus_test', items=[{'plan': 'plan_test'}],
            trial_period_days=30, idempotency_key='subscription-test-key')
        self.assertEqual(subscription.id, 'sub_test')
        args, kwargs = self.client.request_with_retries.call_args
        self.assertEqual(args[:2], ('post', 'https://api.stripe.com/v1/subscriptions'))
        self.assertEqual(args[2]['Idempotency-Key'], 'subscription-test-key')
        self.assertNotIn('Stripe-Version', args[2])
        self.assertEqual(parse_qs(args[3])['trial_period_days'], ['30'])
        self.assertEqual(parse_qs(args[3])['items[0][plan]'], ['plan_test'])
