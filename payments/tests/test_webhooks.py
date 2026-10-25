import copy
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from payments.models import StripeWebhookEvent
from profile.models import Profile


@override_settings(SECURE_SSL_REDIRECT=False, ENDPOINT_SECRET_KEY='whsec_webhook_tests')
class StripeWebhookReliabilityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='webhook_owner')
        self.profile = self.user.profile
        self.profile.customer_id = 'cus_owner'
        self.profile.subscription_id = 'sub_current'
        self.profile.active = True
        self.profile.expired = False
        self.profile.save()
        self.end = int(time.time()) + 30 * 24 * 60 * 60
        self.subscriptions = {'sub_current': self.subscription('sub_current', 100)}
        patcher = patch('payments.webhooks.stripe.Subscription.retrieve', side_effect=self.retrieve_subscription)
        self.retrieve = patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch('payments.webhooks.stripe.Subscription.modify')
        self.modify = patcher.start()
        self.addCleanup(patcher.stop)
        self.client = Client(enforce_csrf_checks=True)
        self.url = reverse('stripe_webhook')

    def subscription(self, subscription_id, created, **overrides):
        data = {
            'id': subscription_id, 'customer': 'cus_owner', 'created': created,
            'status': 'active', 'current_period_end': self.end,
            'cancel_at_period_end': False,
            'items': {'data': [{'plan': {'interval': 'month'}}]},
        }
        data.update(overrides)
        return data

    def retrieve_subscription(self, subscription_id, **kwargs):
        return copy.deepcopy(self.subscriptions[subscription_id])

    def event(self, event_id='evt_current', event_type='customer.subscription.updated', **values):
        obj = {'id': 'sub_current', 'customer': 'cus_owner', 'status': 'active'}
        obj.update(values)
        return {'id': event_id, 'object': 'event', 'type': event_type,
                'created': int(time.time()), 'data': {'object': obj}}

    def send(self, event):
        body = json.dumps(event).encode()
        stamp = str(int(time.time()))
        digest = hmac.new(b'whsec_webhook_tests', stamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
        return self.client.post(self.url, body, content_type='application/json',
                                HTTP_STRIPE_SIGNATURE=f't={stamp},v1={digest}')

    def checkout(self, event_id='evt_checkout', subscription='sub_new', **values):
        return self.event(event_id, 'checkout.session.completed', id='cs_owner',
                          subscription=subscription, mode='subscription',
                          payment_status=values.pop('payment_status', 'paid'), **values)

    def test_valid_signed_event_updates_profile_and_records_receipt(self):
        self.profile.expired = True
        self.profile.save(update_fields=['expired'])
        response = self.send(self.event())

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.active)
        self.assertFalse(self.profile.expired)
        self.assertEqual(self.profile.end_date, datetime.fromtimestamp(self.end, tz=timezone.utc).date())
        self.assertTrue(StripeWebhookEvent.objects.filter(event_id='evt_current').exists())
        self.modify.assert_not_called()

    def test_duplicate_event_does_not_repeat_processing(self):
        event = self.event()
        self.assertEqual(self.send(event).status_code, 200)
        self.assertEqual(self.send(event).status_code, 200)

        self.assertEqual(self.retrieve.call_count, 1)
        self.assertEqual(StripeWebhookEvent.objects.count(), 1)

    def test_missing_signature_is_rejected(self):
        response = self.client.post(self.url, '{}', content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.retrieve.assert_not_called()
        self.assertFalse(StripeWebhookEvent.objects.exists())

    def test_invalid_signature_is_rejected(self):
        response = self.client.post(self.url, json.dumps(self.event()), content_type='application/json',
                                    HTTP_STRIPE_SIGNATURE='t=1,v1=invalid')

        self.assertEqual(response.status_code, 400)
        self.retrieve.assert_not_called()

    def test_get_is_rejected(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.retrieve.assert_not_called()

    def test_unhandled_event_needs_no_customer_and_is_acknowledged(self):
        event = self.event(event_type='product.updated')
        event['data']['object'] = {'id': 'prod_unrelated'}
        self.assertEqual(self.send(event).status_code, 200)
        self.retrieve.assert_not_called()

    def test_generic_charge_cannot_grant_or_revoke_subscription_access(self):
        self.profile.active = False
        self.profile.expired = True
        self.profile.save()
        for kind in ('charge.succeeded', 'charge.failed'):
            with self.subTest(kind=kind):
                self.assertEqual(self.send(self.event(event_type=kind)).status_code, 200)
                self.profile.refresh_from_db()
                self.assertFalse(self.profile.active)
                self.assertTrue(self.profile.expired)
        self.retrieve.assert_not_called()

    def test_delayed_active_snapshot_cannot_reactivate_canceled_subscription(self):
        self.subscriptions['sub_current']['status'] = 'canceled'
        self.assertEqual(self.send(self.event(status='active')).status_code, 200)

        self.profile.refresh_from_db()
        self.assertFalse(self.profile.active)
        self.assertFalse(self.profile.trial)
        self.assertTrue(self.profile.canceled)
        self.assertTrue(self.profile.expired)

    def test_out_of_order_distinct_events_use_current_state(self):
        self.subscriptions['sub_current']['status'] = 'unpaid'
        newer = self.event('evt_newer', status='unpaid')
        older = self.event('evt_older', status='active')
        older['created'] -= 100
        self.assertEqual(self.send(newer).status_code, 200)
        self.assertEqual(self.send(older).status_code, 200)

        self.profile.refresh_from_db()
        self.assertFalse(self.profile.active)
        self.assertTrue(self.profile.expired)
        self.assertEqual(self.retrieve.call_count, 2)

    def test_deleted_old_subscription_cannot_cancel_current_one(self):
        event = self.event(event_type='customer.subscription.deleted', id='sub_old')
        self.assertEqual(self.send(event).status_code, 200)

        self.profile.refresh_from_db()
        self.assertTrue(self.profile.active)
        self.assertEqual(self.profile.subscription_id, 'sub_current')
        self.retrieve.assert_not_called()

    def test_old_subscription_invoice_cannot_change_current_access(self):
        self.profile.active = False
        self.profile.save(update_fields=['active'])
        event = self.event(event_type='invoice.payment_succeeded', id='in_old', subscription='sub_old')
        self.assertEqual(self.send(event).status_code, 200)

        self.profile.refresh_from_db()
        self.assertFalse(self.profile.active)
        self.retrieve.assert_not_called()

    def test_delayed_payment_failure_uses_recovered_subscription_state(self):
        event = self.event(event_type='invoice.payment_failed', id='in_current', subscription='sub_current')
        self.assertEqual(self.send(event).status_code, 200)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.active)
        self.assertFalse(self.profile.expired)

    def test_unknown_customer_is_retryable_and_not_marked_processed(self):
        with self.assertLogs('django.payments.webhooks', level='ERROR'):
            response = self.send(self.event(customer='cus_unknown'))
        self.assertEqual(response.status_code, 503)
        self.assertFalse(StripeWebhookEvent.objects.exists())

    def test_stripe_failure_can_retry_same_event(self):
        self.retrieve.side_effect = TimeoutError('Stripe unavailable')
        with self.assertLogs('django.payments.webhooks', level='ERROR'):
            response = self.send(self.event())
        self.assertEqual(response.status_code, 503)
        self.assertFalse(StripeWebhookEvent.objects.exists())
        self.retrieve.side_effect = self.retrieve_subscription
        self.assertEqual(self.send(self.event()).status_code, 200)
        self.assertEqual(StripeWebhookEvent.objects.count(), 1)

    def test_local_save_failure_rolls_back_receipt_and_profile(self):
        with patch.object(Profile, 'save', side_effect=RuntimeError('Database write failed')):
            with self.assertLogs('django.payments.webhooks', level='ERROR'):
                response = self.send(self.event())
        self.assertEqual(response.status_code, 503)
        self.assertFalse(StripeWebhookEvent.objects.exists())
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.end_date)
        self.assertEqual(self.send(self.event()).status_code, 200)

    def test_subscription_customer_mismatch_is_retryable(self):
        self.subscriptions['sub_current']['customer'] = 'cus_someone_else'
        with self.assertLogs('django.payments.webhooks', level='ERROR'):
            response = self.send(self.event())
        self.assertEqual(response.status_code, 503)
        self.assertFalse(StripeWebhookEvent.objects.exists())

    def test_checkout_adopts_only_newer_subscription_without_modifying_stripe(self):
        self.subscriptions['sub_new'] = self.subscription('sub_new', 200)
        self.assertEqual(self.send(self.checkout()).status_code, 200)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.subscription_id, 'sub_new')
        self.assertTrue(self.profile.active)
        self.modify.assert_not_called()
        self.assertEqual(self.send(self.checkout()).status_code, 200)
        self.assertEqual(self.retrieve.call_count, 2)

    def test_delayed_checkout_cannot_replace_newer_subscription(self):
        self.subscriptions['sub_old'] = self.subscription('sub_old', 50)
        self.assertEqual(self.send(self.checkout(subscription='sub_old')).status_code, 200)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.subscription_id, 'sub_current')
        self.modify.assert_not_called()

    def test_unpaid_checkout_does_not_grant_access(self):
        self.assertEqual(self.send(self.checkout(payment_status='unpaid')).status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.subscription_id, 'sub_current')
        self.retrieve.assert_not_called()

    def test_cancel_at_period_end_preserves_access_while_active(self):
        self.subscriptions['sub_current']['cancel_at_period_end'] = True
        self.assertEqual(self.send(self.event()).status_code, 200)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.active)
        self.assertTrue(self.profile.canceled)

    def test_trial_status_clears_paid_access_and_sets_trial_warning(self):
        self.subscriptions['sub_current'].update(
            status='trialing', trial_end=int(time.time()) + 2 * 24 * 60 * 60,
        )
        self.assertEqual(self.send(self.event(event_type='customer.subscription.trial_will_end')).status_code, 200)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.trial)
        self.assertTrue(self.profile.trial_expiring)
        self.assertFalse(self.profile.active)

    def test_item_level_billing_period_is_supported(self):
        sub = self.subscriptions['sub_current']
        sub.pop('current_period_end')
        sub['items']['data'][0]['current_period_end'] = self.end
        self.assertEqual(self.send(self.event()).status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.end_date, datetime.fromtimestamp(self.end, tz=timezone.utc).date())

    def test_new_invoice_subscription_shape_is_supported(self):
        event = self.event(event_type='invoice.paid', id='in_current',
                           parent={'subscription_details': {'subscription': 'sub_current'}})
        self.assertEqual(self.send(event).status_code, 200)
        self.retrieve.assert_called_once()

    def test_one_off_invoice_is_acknowledged_without_changing_access(self):
        self.assertEqual(self.send(self.event(event_type='invoice.paid', id='in_one_off')).status_code, 200)
        self.retrieve.assert_not_called()

    def test_missing_subscription_mapping_retries_provisioning_race(self):
        self.profile.subscription_id = ''
        self.profile.save(update_fields=['subscription_id'])
        with self.assertLogs('django.payments.webhooks', level='ERROR'):
            response = self.send(self.event(event_type='customer.subscription.created'))
        self.assertEqual(response.status_code, 503)
        self.assertFalse(StripeWebhookEvent.objects.exists())

    def test_active_subscription_without_period_is_not_granted_access(self):
        self.subscriptions['sub_current'].pop('current_period_end')
        with self.assertLogs('django.payments.webhooks', level='ERROR'):
            response = self.send(self.event())
        self.assertEqual(response.status_code, 503)
        self.assertFalse(StripeWebhookEvent.objects.exists())

    def test_equal_checkout_subscription_timestamps_require_review(self):
        self.subscriptions['sub_new'] = self.subscription('sub_new', 100)
        with self.assertLogs('django.payments.webhooks', level='ERROR'):
            response = self.send(self.checkout())
        self.assertEqual(response.status_code, 503)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.subscription_id, 'sub_current')
        self.assertFalse(StripeWebhookEvent.objects.exists())
