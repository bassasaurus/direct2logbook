from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from payments.models import StripeWebhookEvent, StripeWebhookFailure
from payments.webhook_monitoring import record_webhook_failure


@override_settings(
    STRIPE_WEBHOOK_ALERT_EMAIL='admin@example.com',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class WebhookMonitoringTests(TestCase):
    def failure(self, event_id='evt_failed', attempts=3):
        return StripeWebhookFailure.objects.create(
            event_id=event_id, event_type='invoice.payment_succeeded',
            attempts=attempts, last_failed_at=timezone.now(),
        )

    def check(self):
        call_command('check_stripe_webhooks', stdout=StringIO())

    def test_repeated_failures_send_one_alert_then_cool_down(self):
        failure = self.failure()
        self.check()
        self.check()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['admin@example.com'])
        self.assertIn(failure.event_id, mail.outbox[0].body)
        failure.refresh_from_db()
        self.assertIsNotNone(failure.last_alerted_at)

    def test_single_transient_failure_does_not_alert(self):
        self.failure(attempts=1)
        self.check()
        self.assertEqual(len(mail.outbox), 0)

    def test_old_single_failure_alerts_even_without_further_deliveries(self):
        failure = self.failure(attempts=1)
        StripeWebhookFailure.objects.filter(pk=failure.pk).update(
            first_failed_at=timezone.now() - timedelta(minutes=16),
        )
        self.check()
        self.assertEqual(len(mail.outbox), 1)

    def test_success_receipt_stops_alerts(self):
        failure = self.failure()
        StripeWebhookEvent.objects.create(
            event_id=failure.event_id, event_type=failure.event_type,
        )
        self.check()
        self.assertEqual(len(mail.outbox), 0)

    def test_unresolved_failure_alerts_again_after_an_hour(self):
        failure = self.failure()
        self.check()
        StripeWebhookFailure.objects.filter(pk=failure.pk).update(
            last_alerted_at=timezone.now() - timedelta(hours=2),
        )
        self.check()
        self.assertEqual(len(mail.outbox), 2)

    @patch('payments.management.commands.check_stripe_webhooks.send_mail', side_effect=OSError('unavailable'))
    def test_email_failure_does_not_suppress_next_alert(self, send):
        failure = self.failure()
        with self.assertRaises(OSError):
            self.check()
        failure.refresh_from_db()
        self.assertIsNone(failure.last_alerted_at)

    @override_settings(STRIPE_WEBHOOK_ALERT_EMAIL='')
    def test_missing_recipient_is_reported(self):
        with self.assertRaises(CommandError):
            self.check()

    def test_failure_tracking_counts_attempts_without_storing_payload(self):
        event = {'id': 'evt_failed', 'type': 'invoice.payment_failed',
                 'data': {'customer_email': 'private@example.com'}}
        record_webhook_failure(event)
        record_webhook_failure(event)
        failure = StripeWebhookFailure.objects.get()
        self.assertEqual(failure.attempts, 2)
        self.assertEqual(failure.event_type, 'invoice.payment_failed')

    @patch('payments.webhook_monitoring.StripeWebhookFailure.objects.get_or_create', side_effect=OSError)
    def test_monitoring_failure_does_not_escape_to_request(self, create):
        record_webhook_failure({'id': 'evt_failed', 'type': 'invoice.payment_failed'})
