from datetime import timedelta
from io import StringIO
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from csv_app.models import CSVImportBatch
from operations.models import BackgroundJobMonitor
from payments.models import BillingProvisioning
from pdf_output.models import PDFRequest


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   BACKGROUND_JOB_ALERT_EMAIL='admin@example.com')
class BackgroundJobMonitoringTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='monitor-user', email='private@example.com')
        self.now = timezone.now()

    def check(self, *args):
        output = StringIO()
        call_command('check_background_jobs', *args, stdout=output)
        return output.getvalue()

    def pdf(self, status, minutes=0):
        job = PDFRequest.objects.create(user=self.user, task_id=str(uuid.uuid4()), status=status)
        PDFRequest.objects.filter(pk=job.pk).update(updated_at=self.now - timedelta(minutes=minutes))
        return job

    def csv(self, status, minutes=0, completed=False):
        return CSVImportBatch.objects.create(user=self.user, content='private CSV payload', row_count=1,
            status=status, completed=completed, error_message='private exception',
            updated_at=self.now - timedelta(minutes=minutes))

    def billing(self, status, minutes=0, **kwargs):
        job = BillingProvisioning.objects.create(user=self.user, status=status,
                                                 last_error='private Stripe error', **kwargs)
        BillingProvisioning.objects.filter(pk=job.pk).update(updated_at=self.now - timedelta(minutes=minutes))
        return job

    def test_healthy_and_recent_work_send_no_email(self):
        self.pdf('sent', 200)
        for status in ('queued', 'unconfirmed', 'processing', 'retrying', 'sending'):
            self.pdf(status)
        self.csv('preview', 100)
        self.csv('completed', completed=True)
        for status in ('queued', 'unconfirmed', 'processing'):
            self.csv(status)
        self.billing('processing', processing_started_at=self.now)
        self.assertIn('No background jobs', self.check())
        self.assertEqual(mail.outbox, [])

    def test_combines_failures_without_private_data_or_source_mutations(self):
        pdf = self.pdf('failed')
        csv = self.csv('failed')
        billing = self.billing('failed', outcome_uncertain=True)
        with patch('payments.services.stripe.Customer.create') as stripe, patch(
            'payments.tasks.provision_trial_task.apply_async'
        ) as publish:
            self.assertIn('3 unresolved', self.check())
        stripe.assert_not_called()
        publish.assert_not_called()
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        for label in ('PDF:', 'CSV:', 'Trial provisioning:'):
            self.assertIn(label, body)
        for private in ('private@example.com', 'private CSV payload', 'private exception', 'private Stripe error'):
            self.assertNotIn(private, body)
        for job in (pdf, csv, billing):
            job.refresh_from_db()
            self.assertEqual(job.status, 'failed')
        self.assertEqual(csv.content, 'private CSV payload')
        self.assertEqual(mail.outbox[0].to, ['admin@example.com'])

    def test_each_stalled_pdf_state_is_reported(self):
        for status in ('queued', 'unconfirmed', 'processing', 'retrying', 'sending'):
            self.pdf(status, 16)
        self.assertIn('5 unresolved', self.check())

    def test_each_stalled_csv_state_is_reported(self):
        for status in ('queued', 'unconfirmed', 'processing'):
            self.csv(status, 21)
        self.assertIn('3 unresolved', self.check())

    def test_pending_trial_publication_stalls_after_fifteen_minutes(self):
        self.billing('pending', 16)
        self.assertIn('1 unresolved', self.check())

    def test_stalled_billing_uses_processing_start_not_recent_updates(self):
        self.billing('processing', processing_started_at=self.now - timedelta(minutes=16))
        self.assertIn('1 unresolved', self.check())

    def test_processing_without_start_is_reported(self):
        self.billing('processing')
        self.assertIn('1 unresolved', self.check())

    def test_old_pdf_csv_failures_expire_but_uncertainty_and_billing_remain(self):
        self.pdf('failed', 1500)
        self.csv('failed', 1500)
        self.pdf('delivery_uncertain', 1500)
        self.billing('failed', 1500)
        self.assertIn('2 unresolved', self.check())

    def test_same_problems_repeat_only_after_an_hour(self):
        self.pdf('failed')
        self.check()
        self.assertIn('cooldown', self.check())
        self.assertEqual(len(mail.outbox), 1)
        BackgroundJobMonitor.objects.update(last_alerted_at=self.now - timedelta(hours=2))
        self.check()
        self.assertEqual(len(mail.outbox), 2)

    def test_recovered_jobs_stop_alerts(self):
        job = self.pdf('failed')
        self.check()
        PDFRequest.objects.filter(pk=job.pk).update(status='sent')
        self.assertIn('No background jobs', self.check())
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(BACKGROUND_JOB_ALERT_EMAIL='')
    def test_disabled_recipient_errors_but_dry_run_has_no_writes(self):
        self.pdf('failed')
        with self.assertRaises(CommandError):
            self.check()
        self.assertIn('1. No email or state changes.', self.check('--dry-run'))
        self.assertFalse(BackgroundJobMonitor.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_send_test_does_not_advance_cooldown(self):
        self.assertIn('test email sent', self.check('--send-test'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('monitor test', mail.outbox[0].subject)
        self.assertFalse(BackgroundJobMonitor.objects.exists())

    def test_mail_error_or_zero_result_does_not_suppress_next_attempt(self):
        self.pdf('failed')
        for kwargs in ({'side_effect': RuntimeError('private credential')}, {'return_value': 0}):
            with self.subTest(kwargs=kwargs), patch(
                'operations.management.commands.check_background_jobs.send_mail', **kwargs,
            ), self.assertRaises(CommandError) as raised:
                self.check()
            self.assertNotIn('private credential', str(raised.exception))
            self.assertFalse(BackgroundJobMonitor.objects.exists())
        self.check()
        self.assertEqual(len(mail.outbox), 1)

    def test_details_are_bounded_with_total_count(self):
        for index in range(35):
            self.pdf('failed')
        self.check()
        self.assertIn('PDF: 35', mail.outbox[0].body)
        self.assertIn('Showing oldest 30 of 35.', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].body.count('id='), 30)
