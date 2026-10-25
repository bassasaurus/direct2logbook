import uuid
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from pdf_output.models import PDFRequest
from pdf_output.pdf_generate_task import pdf_generate


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PDFStaleRecoveryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='pdf_stale', email='stale@example.com')

    def job(self, status, stale=True, attempts=0):
        job = PDFRequest.objects.create(user=self.user, task_id=str(uuid.uuid4()),
                                        status=status, render_attempts=attempts)
        if stale:
            PDFRequest.objects.filter(pk=job.pk).update(updated_at=timezone.now() - timedelta(minutes=16))
        return job

    def reconcile(self, dry_run=False):
        output = StringIO()
        call_command('reconcile_pdf_requests', dry_run=dry_run, stdout=output)
        return output.getvalue()

    def run_job(self, job):
        pdf_generate.run(self.user.pk, request_id=str(job.pk))
        job.refresh_from_db()

    def expire_running_job(self, job):
        PDFRequest.objects.filter(pk=job.pk).update(updated_at=timezone.now() - timedelta(minutes=16))
        with self.assertLogs('django.pdf_output', level='WARNING'):
            self.reconcile()

    def test_stale_pre_send_requests_are_closed_for_manual_retry(self):
        jobs = [self.job(status) for status in ('queued', 'unconfirmed', 'processing', 'retrying')]
        with self.assertLogs('django.pdf_output', level='WARNING'):
            self.reconcile()
        for job in jobs:
            job.refresh_from_db()
            self.assertEqual(job.status, PDFRequest.Status.FAILED)

    def test_stale_sending_becomes_uncertain(self):
        job = self.job(PDFRequest.Status.SENDING, attempts=1)
        with self.assertLogs('django.pdf_output', level='WARNING'):
            self.reconcile()
        job.refresh_from_db()
        self.assertEqual(job.status, PDFRequest.Status.UNCERTAIN)

    def test_fresh_and_terminal_requests_are_unchanged(self):
        jobs = [self.job(status, stale=False) for status in ('queued', 'processing', 'retrying', 'sending')]
        jobs += [self.job(status) for status in ('sent', 'failed', 'delivery_uncertain')]
        self.reconcile()
        for job in jobs:
            expected = job.status
            job.refresh_from_db()
            self.assertEqual(job.status, expected)

    def test_dry_run_does_not_mutate_and_repeated_recovery_is_safe(self):
        job = self.job(PDFRequest.Status.PROCESSING, attempts=1)
        self.assertIn('Stale before sending: 1', self.reconcile(dry_run=True))
        job.refresh_from_db()
        self.assertEqual(job.status, PDFRequest.Status.PROCESSING)
        with self.assertLogs('django.pdf_output', level='WARNING'):
            self.reconcile()
        job.refresh_from_db()
        closed_at = job.updated_at
        self.assertIn('failed=0, delivery_uncertain=0', self.reconcile())
        job.refresh_from_db()
        self.assertEqual(job.updated_at, closed_at)

    @patch('pdf_output.pdf_generate_task._build_pdf')
    def test_late_delivery_of_closed_queued_job_is_ignored(self, render):
        job = self.job(PDFRequest.Status.QUEUED)
        with self.assertLogs('django.pdf_output', level='WARNING'):
            self.reconcile()
        self.run_job(job)
        render.assert_not_called()
        self.assertEqual(job.status, PDFRequest.Status.FAILED)

    @patch('pdf_output.pdf_generate_task.EmailMessage.send')
    def test_old_renderer_cannot_send_after_monitor_closes_its_attempt(self, send):
        job = self.job(PDFRequest.Status.QUEUED, stale=False)
        def render(user):
            self.expire_running_job(job)
            return b'%PDF-test'
        with patch('pdf_output.pdf_generate_task._build_pdf', side_effect=render):
            self.run_job(job)
        self.assertEqual(job.status, PDFRequest.Status.FAILED)
        send.assert_not_called()

    @patch.object(pdf_generate, 'retry')
    def test_old_renderer_cannot_reopen_closed_attempt_for_retry(self, retry):
        job = self.job(PDFRequest.Status.QUEUED, stale=False)
        def render(user):
            self.expire_running_job(job)
            raise ConnectionError('temporary')
        with patch('pdf_output.pdf_generate_task._build_pdf', side_effect=render):
            with self.assertRaises(ConnectionError):
                self.run_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, PDFRequest.Status.FAILED)
        retry.assert_not_called()

    @patch('pdf_output.pdf_generate_task._build_pdf', return_value=b'%PDF-test')
    def test_late_confirmed_mail_acceptance_can_resolve_uncertainty(self, render):
        job = self.job(PDFRequest.Status.QUEUED, stale=False)
        def send(**kwargs):
            self.expire_running_job(job)
            return 1
        with patch('pdf_output.pdf_generate_task.EmailMessage.send', side_effect=send) as send_email:
            self.run_job(job)
            self.run_job(job)
        self.assertEqual(job.status, PDFRequest.Status.SENT)
        self.assertEqual(send_email.call_count, 1)

    @patch('pdf_output.pdf_generate_task._build_pdf', return_value=b'%PDF-test')
    def test_late_mail_failure_does_not_erase_uncertainty(self, render):
        job = self.job(PDFRequest.Status.QUEUED, stale=False)
        def send(**kwargs):
            self.expire_running_job(job)
            raise TimeoutError('unknown delivery')
        with patch('pdf_output.pdf_generate_task.EmailMessage.send', side_effect=send):
            with self.assertLogs('pdf_output.pdf_generate_task', level='ERROR'):
                with self.assertRaises(TimeoutError):
                    self.run_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, PDFRequest.Status.UNCERTAIN)
