from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
import re

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from payments.checkout import SALT


@override_settings(SECURE_SSL_REDIRECT=False, PLAN_MONTHLY='price_month', PLAN_YEARLY='price_year')
class OnDemandCheckoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='checkout_owner')
        self.other = get_user_model().objects.create_user(username='checkout_other')
        p = self.user.profile
        p.customer_id = 'cus_owner'
        p.subscription_id = 'sub_trial'
        p.trial = True
        p.end_date = timezone.now().date() + timedelta(days=7)
        p.save()
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.url = reverse('start_checkout')
        create_patch = patch('payments.checkout.stripe.checkout.Session.create', return_value={
                             'id': 'cs_test', 'url': 'https://checkout.stripe.com/c/pay/cs_test'})
        self.create = create_patch.start()
        self.addCleanup(create_patch.stop)
        subscription_patch = patch('payments.checkout.stripe.Subscription.list', return_value=SimpleNamespace(auto_paging_iter=lambda: iter([
            {'id': 'sub_trial', 'status': 'trialing'}, {'id': 'sub_old', 'status': 'canceled'}])))
        self.subscriptions = subscription_patch.start()
        self.addCleanup(subscription_patch.stop)

    def form(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        return {'csrfmiddlewaretoken': re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)[1],
                'checkout_request': re.search(r'name="checkout_request" value="([^"]+)"', html)[1], 'plan': 'monthly'}

    def test_profile_loads_without_any_checkout_or_subscription_api_calls(self):
        self.create.side_effect = stripe.error.APIConnectionError('Stripe unavailable')
        self.form()
        self.create.assert_not_called()
        self.subscriptions.assert_not_called()

    def test_clicked_plan_uses_authenticated_customer_and_server_price(self):
        for plan, price in [('monthly', settings.PLAN_MONTHLY), ('yearly', settings.PLAN_YEARLY)]:
            data = {**self.form(), 'plan': plan, 'customer': 'cus_other', 'user': self.other.pk,
                    'price': 'price_forged', 'success_url': 'https://evil.example'}
            response = self.client.post(self.url, data)
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response['Location'], 'https://checkout.stripe.com/c/pay/cs_test')
            args = self.create.call_args.kwargs
            self.assertEqual(args['customer'], 'cus_owner')
            self.assertEqual(args['line_items'], [{'price': price, 'quantity': 1}])
            self.assertEqual(args['mode'], 'subscription')
            self.assertEqual(args['client_reference_id'], str(self.user.pk))
            self.assertNotIn('evil.example', args['success_url'])
            self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.create.call_count, 2)

    def test_repeated_form_submission_reuses_stripe_idempotency_key(self):
        data = self.form()
        first = self.client.post(self.url, data)
        key = self.create.call_args.kwargs['idempotency_key']
        second = self.client.post(self.url, data)
        self.assertEqual(first.status_code, 303)
        self.assertEqual(second.status_code, 303)
        self.assertEqual(key, self.create.call_args.kwargs['idempotency_key'])

    def test_get_and_missing_csrf_cannot_create_sessions(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(self.client.post(self.url, {'plan': 'monthly'}).status_code, 403)
        self.create.assert_not_called()
        self.subscriptions.assert_not_called()

    def test_anonymous_post_requires_login(self):
        self.assertEqual(Client().post(self.url, {'plan': 'monthly'}).status_code, 302)
        self.create.assert_not_called()

    def test_invalid_plan_and_tampered_or_cross_account_intent_are_rejected(self):
        data = self.form()
        other_token = signing.dumps({'user': self.other.pk, 'nonce': 'a'*32}, salt=SALT)
        for changed in [{'plan': 'invalid'}, {'checkout_request': 'bad'}, {'checkout_request': other_token}]:
            self.assertEqual(self.client.post(self.url, {**data, **changed}).status_code, 400)
        self.create.assert_not_called()
        self.subscriptions.assert_not_called()

    def test_expired_intent_is_rejected_without_contacting_stripe(self):
        data = self.form()
        with patch('django.core.signing.time.time', return_value=0):
            data['checkout_request'] = signing.dumps(
                {'user': self.user.pk, 'nonce': 'a'*32}, salt=SALT)
        self.assertEqual(self.client.post(self.url, data).status_code, 400)
        self.create.assert_not_called()

    def test_free_and_unprovisioned_accounts_cannot_checkout(self):
        data = self.form()
        self.user.profile.free_access = True
        self.user.profile.save()
        self.assertEqual(self.client.post(self.url, data).status_code, 409)
        self.user.profile.free_access = False
        self.user.profile.customer_id = ''
        self.user.profile.save()
        self.assertEqual(self.client.post(self.url, data).status_code, 409)
        self.create.assert_not_called()

    def test_stripe_active_subscription_blocks_second_purchase_even_before_webhook(self):
        data = self.form()
        for state in ['active', 'past_due', 'unpaid', 'incomplete', 'paused', 'trialing']:
            self.subscriptions.return_value = SimpleNamespace(
                auto_paging_iter=lambda state=state: iter([{'id': 'sub_new', 'status': state}]))
            self.assertEqual(self.client.post(self.url, data).status_code, 409)
        self.create.assert_not_called()

    def test_stripe_failure_preserves_subscription_and_offers_same_intent_retry(self):
        data = self.form()
        self.create.side_effect = stripe.error.APIConnectionError('unavailable')
        with self.assertLogs('payments.checkout', level='ERROR'):
            response = self.client.post(self.url, data)
        self.assertContains(response, 'Try again', status_code=503)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.subscription_id, 'sub_trial')
        self.assertTrue(self.user.profile.trial)
        self.assertEqual(response.context['checkout_request'], data['checkout_request'])

    def test_non_stripe_checkout_redirect_is_rejected(self):
        data = self.form()
        self.create.return_value = {'url': 'https://evil.example/checkout'}
        with self.assertLogs('payments.checkout', level='ERROR'):
            response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('Location', response)

    def test_uncertain_provisioning_blocks_checkout_and_active_profile_has_no_switch_button(self):
        from payments.models import BillingProvisioning
        data = self.form()
        BillingProvisioning.objects.create(user=self.user, outcome_uncertain=True)
        self.assertEqual(self.client.post(self.url, data).status_code, 409)
        self.create.assert_not_called()
        self.subscriptions.assert_not_called()
        p = self.user.profile
        p.active = True
        p.trial = False
        p.monthly = True
        p.save()
        response = self.client.get(reverse('profile'))
        self.assertNotContains(response, 'Switch to yearly')
        self.assertContains(response, 'Cancel subscription')
