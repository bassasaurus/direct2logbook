import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from kombu.exceptions import OperationalError

from pdf_output.models import PDFRequest
from pdf_output.pdf_generate_task import pdf_generate


@override_settings(SECURE_SSL_REDIRECT=False, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PDFTrackingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='pdf_tracking', email='pdf@example.com')
        self.other = get_user_model().objects.create_user(username='other_pdf_tracking')
        self.job = PDFRequest.objects.create(user=self.user, task_id=str(uuid.uuid4()))
        self.url = reverse('pdf_status', args=[self.job.pk])
        self.client.force_login(self.user)

    def run_job(self):
        pdf_generate.run(self.user.pk, request_id=str(self.job.pk))
        self.job.refresh_from_db()

    def test_status_is_owner_scoped_and_not_cacheable(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'queued')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_status_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_status_cannot_be_modified_with_post(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_missing_status_is_404(self):
        self.assertEqual(self.client.get(reverse('pdf_status', args=[uuid.uuid4()])).status_code, 404)

    @patch('pdf_output.pdf_generate_task._build_pdf', return_value=b'%PDF-test')
    def test_success_sends_attachment_once_and_records_provider_acceptance(self, render):
        self.run_job()
        self.run_job()
        self.assertEqual(self.job.status, PDFRequest.Status.SENT)
        self.assertEqual(render.call_count, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertEqual(mail.outbox[0].attachments[0][1], b'%PDF-test')
        self.assertIn(str(self.job.pk), mail.outbox[0].extra_headers['Message-ID'])
        status = self.client.get(self.url).json()
        self.assertEqual(status['message'], 'Check your email')
        self.assertGreater(status['hide_after_ms'], 0)
        self.assertLessEqual(status['hide_after_ms'], 30000)

    @patch('pdf_output.pdf_generate_task._build_pdf', side_effect=RuntimeError('render error'))
    @patch('pdf_output.pdf_generate_task.EmailMessage.send')
    def test_render_failure_is_recorded_without_sending(self, send, render):
        with self.assertLogs('pdf_output.pdf_generate_task', level='ERROR') as logs:
            with self.assertRaises(RuntimeError):
                self.run_job()
        self.assertIn(f'PDF request failed request_id={self.job.pk}', logs.output[0])
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, PDFRequest.Status.FAILED)
        send.assert_not_called()
        self.assertNotIn('render error', self.client.get(self.url).content.decode())

    @patch('pdf_output.pdf_generate_task._build_pdf', return_value=b'%PDF-test')
    @patch('pdf_output.pdf_generate_task.EmailMessage.send', side_effect=TimeoutError('mail timeout'))
    def test_ambiguous_send_is_not_replayed(self, send, render):
        with self.assertLogs('pdf_output.pdf_generate_task', level='ERROR') as logs:
            with self.assertRaises(TimeoutError):
                self.run_job()
        self.assertIn(f'PDF request failed request_id={self.job.pk}', logs.output[0])
        self.run_job()
        self.assertEqual(self.job.status, PDFRequest.Status.UNCERTAIN)
        self.assertEqual(send.call_count, 1)

    @patch('pdf_output.pdf_generate_task._build_pdf', return_value=b'%PDF-test')
    @patch('pdf_output.pdf_generate_task.EmailMessage.send', return_value=0)
    def test_zero_messages_submitted_is_failure(self, send, render):
        with self.assertLogs('pdf_output.pdf_generate_task', level='ERROR') as logs:
            with self.assertRaises(RuntimeError):
                self.run_job()
        self.assertIn(f'PDF request failed request_id={self.job.pk}', logs.output[0])
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, PDFRequest.Status.FAILED)

    @patch('pdf_output.pdf_generate_task._build_pdf')
    def test_another_users_job_cannot_be_run(self, render):
        with self.assertRaises(ValueError):
            pdf_generate.run(self.other.pk, request_id=str(self.job.pk))
        render.assert_not_called()

    @patch('pdf_output.pdf_generate_task._build_pdf')
    def test_duplicate_processing_or_sending_tasks_are_not_claimed(self, render):
        for status in (PDFRequest.Status.PROCESSING, PDFRequest.Status.SENDING):
            PDFRequest.objects.filter(pk=self.job.pk).update(status=status)
            self.run_job()
            self.assertEqual(self.job.status, status)
        render.assert_not_called()

    def test_stale_sending_is_reported_as_uncertain(self):
        PDFRequest.objects.filter(pk=self.job.pk).update(
            status=PDFRequest.Status.SENDING, updated_at=timezone.now() - timedelta(minutes=16),
        )
        self.assertEqual(self.client.get(self.url).json()['status'], 'delivery_uncertain')

    def test_stale_processing_is_reported_as_delayed(self):
        PDFRequest.objects.filter(pk=self.job.pk).update(
            status=PDFRequest.Status.PROCESSING, updated_at=timezone.now() - timedelta(minutes=16),
        )
        self.assertEqual(self.client.get(self.url).json()['status'], 'delayed')

    @patch('pdf_output.views.pdf_generate.apply_async', side_effect=OperationalError('broker'))
    def test_unconfirmed_submission_retains_trackable_request(self, publish):
        response = self.client.post(reverse('pdf', args=[self.user.pk]))
        self.assertEqual(response.status_code, 503)
        job = PDFRequest.objects.exclude(pk=self.job.pk).get()
        self.assertEqual(job.status, PDFRequest.Status.UNCONFIRMED)
        self.assertEqual(self.client.get(response.json()['status_url']).json()['status'], 'unconfirmed')

    @patch('pdf_output.pdf_generate_task._build_pdf', return_value=b'%PDF-test')
    def test_unconfirmed_submission_can_still_complete(self, render):
        PDFRequest.objects.filter(pk=self.job.pk).update(status=PDFRequest.Status.UNCONFIRMED)
        self.run_job()
        self.assertEqual(self.job.status, PDFRequest.Status.SENT)

    @patch('pdf_output.pdf_generate_task._build_pdf', return_value=b'%PDF-test')
    def test_old_queued_message_with_only_user_id_remains_supported(self, render):
        task_id = str(uuid.uuid4())
        pdf_generate.push_request(id=task_id)
        try:
            pdf_generate.run(self.user.pk)
            pdf_generate.run(self.user.pk)
        finally:
            pdf_generate.pop_request()
        self.assertEqual(PDFRequest.objects.get(task_id=task_id).status, PDFRequest.Status.SENT)
        self.assertEqual(render.call_count, 1)
