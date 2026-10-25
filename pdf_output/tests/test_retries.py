import uuid
from unittest.mock import patch

from celery.exceptions import Retry, SoftTimeLimitExceeded
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from kombu.exceptions import OperationalError
from botocore.exceptions import ClientError

from pdf_output.models import PDFRequest
from pdf_output.pdf_generate_task import pdf_generate, _retryable_render_error


@override_settings(SECURE_SSL_REDIRECT=False, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PDFRenderRetryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='pdf_retry', email='retry@example.com')
        self.job = PDFRequest.objects.create(user=self.user, task_id=str(uuid.uuid4()))

    def run_attempt(self, retry_number=0):
        pdf_generate.push_request(id=self.job.task_id, retries=retry_number)
        try:
            pdf_generate.run(self.user.pk, request_id=str(self.job.pk))
        finally:
            pdf_generate.pop_request()

    @patch('pdf_output.pdf_generate_task._build_pdf', side_effect=ConnectionError('temporary'))
    @patch.object(pdf_generate, 'retry', side_effect=Retry())
    def test_transient_render_failure_schedules_retry_without_email(self, retry, render):
        with self.assertLogs('pdf_output.pdf_generate_task', level='WARNING'):
            with self.assertRaises(Retry):
                self.run_attempt()
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, PDFRequest.Status.RETRYING)
        self.assertEqual(self.job.render_attempts, 1)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(retry.call_args.kwargs['countdown'], 30)
        self.assertEqual(retry.call_args.kwargs['kwargs'], {'request_id': str(self.job.pk)})
        # A duplicate of the initial attempt must not claim a scheduled retry.
        self.run_attempt()
        self.assertEqual(render.call_count, 1)

    @patch('pdf_output.pdf_generate_task._build_pdf', side_effect=[TimeoutError('temporary'), b'%PDF-test'])
    @patch.object(pdf_generate, 'retry', side_effect=Retry())
    def test_retry_succeeds_once_and_duplicate_retry_does_not_resend(self, retry, render):
        with self.assertLogs('pdf_output.pdf_generate_task', level='WARNING'):
            with self.assertRaises(Retry):
                self.run_attempt()
        self.run_attempt(1)
        self.run_attempt(1)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, PDFRequest.Status.SENT)
        self.assertEqual(self.job.render_attempts, 2)
        self.assertEqual(len(mail.outbox), 1)

    @patch('pdf_output.pdf_generate_task._build_pdf', side_effect=ConnectionError('temporary'))
    @patch.object(pdf_generate, 'retry', side_effect=Retry())
    def test_second_retry_uses_longer_delay(self, retry, render):
        PDFRequest.objects.filter(pk=self.job.pk).update(status=PDFRequest.Status.RETRYING, render_attempts=1)
        with self.assertLogs('pdf_output.pdf_generate_task', level='WARNING'):
            with self.assertRaises(Retry):
                self.run_attempt(1)
        self.assertEqual(retry.call_args.kwargs['countdown'], 60)

    @patch('pdf_output.pdf_generate_task._build_pdf', side_effect=TimeoutError('temporary'))
    @patch.object(pdf_generate, 'retry')
    def test_final_attempt_failure_stops_retrying(self, retry, render):
        PDFRequest.objects.filter(pk=self.job.pk).update(status=PDFRequest.Status.RETRYING, render_attempts=2)
        with self.assertLogs('pdf_output.pdf_generate_task', level='ERROR'):
            with self.assertRaises(TimeoutError):
                self.run_attempt(2)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, PDFRequest.Status.FAILED)
        self.assertEqual(self.job.render_attempts, 3)
        retry.assert_not_called()

    @patch('pdf_output.pdf_generate_task._build_pdf', side_effect=SoftTimeLimitExceeded())
    @patch.object(pdf_generate, 'retry')
    def test_soft_timeout_is_recorded_without_retry(self, retry, render):
        with self.assertLogs('pdf_output.pdf_generate_task', level='ERROR'):
            with self.assertRaises(SoftTimeLimitExceeded):
                self.run_attempt()
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, PDFRequest.Status.FAILED)
        retry.assert_not_called()

    @patch('pdf_output.pdf_generate_task._build_pdf', return_value=b'%PDF-test')
    @patch('pdf_output.pdf_generate_task.EmailMessage.send', side_effect=SoftTimeLimitExceeded())
    @patch.object(pdf_generate, 'retry')
    def test_soft_timeout_during_sending_is_uncertain_and_never_retried(self, retry, send, render):
        with self.assertLogs('pdf_output.pdf_generate_task', level='ERROR'):
            with self.assertRaises(SoftTimeLimitExceeded):
                self.run_attempt()
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, PDFRequest.Status.UNCERTAIN)
        retry.assert_not_called()

    @patch('pdf_output.pdf_generate_task._build_pdf', side_effect=ConnectionError('temporary'))
    @patch.object(pdf_generate, 'retry', side_effect=OperationalError('broker'))
    def test_retry_publish_failure_is_recorded(self, retry, render):
        with self.assertLogs('pdf_output.pdf_generate_task', level='WARNING'):
            with self.assertRaises(OperationalError):
                self.run_attempt()
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, PDFRequest.Status.FAILED)

    @patch('pdf_output.pdf_generate_task._build_pdf', side_effect=ValueError('bad data'))
    @patch.object(pdf_generate, 'retry')
    def test_permanent_render_error_does_not_retry(self, retry, render):
        with self.assertLogs('pdf_output.pdf_generate_task', level='ERROR'):
            with self.assertRaises(ValueError):
                self.run_attempt()
        retry.assert_not_called()

    def test_storage_retry_policy_excludes_permissions_and_missing_files(self):
        for code, status, expected in [('SlowDown', 503, True), ('AccessDenied', 403, False), ('NoSuchKey', 404, False)]:
            exc = ClientError({'Error': {'Code': code}, 'ResponseMetadata': {'HTTPStatusCode': status}}, 'GetObject')
            self.assertEqual(_retryable_render_error(exc), expected)

    def test_retrying_status_is_visible_to_owner(self):
        self.client.force_login(self.user)
        PDFRequest.objects.filter(pk=self.job.pk).update(status=PDFRequest.Status.RETRYING)
        response = self.client.get(reverse('pdf_status', args=[self.job.pk]))
        self.assertEqual(response.json()['status'], 'retrying')
        self.assertIn('automatically', response.json()['message'])

    def test_task_has_explicit_limits_and_retry_budget(self):
        self.assertEqual(pdf_generate.soft_time_limit, 600)
        self.assertEqual(pdf_generate.time_limit, 660)
        self.assertEqual(pdf_generate.max_retries, 2)
