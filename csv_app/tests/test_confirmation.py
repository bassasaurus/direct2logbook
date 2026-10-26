from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from csv_app.csv_import import confirm_csv_import
from csv_app.models import CSVImportBatch
from csv_app.tests.test_atomic_import import content, row
from flights.models import Flight, Approach


@override_settings(SECURE_SSL_REDIRECT=False)
class CSVConfirmationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='batch_owner')
        self.other = get_user_model().objects.create_user(username='batch_other')
        self.client.force_login(self.user)
        self.batch = CSVImportBatch.objects.create(user=self.user, content=content(), row_count=1)

    def confirm(self, batch=None):
        return self.client.post(reverse('csv_upload'), {'batch_id': str((batch or self.batch).pk)})

    def test_repeat_confirmation_returns_receipt_without_more_flights_or_emails(self):
        with patch('csv_app.csv_import.email_confirmation') as notify:
            with self.captureOnCommitCallbacks(execute=True):
                first = self.confirm()
                second = self.confirm()
        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.json()['already_completed'])
        self.assertTrue(second.json()['already_completed'])
        self.assertEqual(Flight.objects.count(), 1)
        self.assertEqual(Approach.objects.count(), 1)
        notify.assert_called_once()
        self.batch.refresh_from_db()
        self.assertTrue(self.batch.completed)
        self.assertEqual(self.batch.content, '')
        self.assertIsNotNone(self.batch.completed_at)

    def test_failed_write_keeps_batch_pending_and_retryable(self):
        with patch('csv_app.csv_import.Approach.objects.create', side_effect=RuntimeError('database write')):
            with self.assertLogs('django.csv_app', level='ERROR'):
                response = self.confirm()
        self.assertEqual(response.status_code, 503)
        self.batch.refresh_from_db()
        self.assertFalse(self.batch.completed)
        self.assertTrue(self.batch.content)
        self.assertFalse(Flight.objects.exists())
        self.assertEqual(self.confirm().status_code, 200)
        self.assertEqual(Flight.objects.count(), 1)

    def test_user_cannot_confirm_someone_elses_batch(self):
        self.client.force_login(self.other)
        self.assertEqual(self.confirm().status_code, 404)
        self.assertFalse(Flight.objects.exists())

    def test_completed_receipt_cannot_be_read_by_another_user(self):
        self.confirm()
        self.client.force_login(self.other)
        self.assertEqual(self.confirm().status_code, 404)

    def test_missing_invalid_and_nonexistent_tokens(self):
        for value in ['', 'bad', str(uuid.uuid4())]:
            response = self.client.post(reverse('csv_upload'), {'batch_id': value})
            self.assertEqual(response.status_code, 404 if len(value) == 36 else 400)

    def test_separate_previews_cannot_overwrite_each_others_content(self):
        upload = SimpleUploadedFile('second.csv', content([row(**{'2': 'N22222'})]).encode())
        preview = self.client.post(reverse('csv_inspect'), {'file': upload})
        second = preview.context['batch']
        self.assertNotEqual(second.pk, self.batch.pk)
        self.confirm(self.batch)
        self.assertEqual(Flight.objects.get().registration.registration, 'N12345')
        self.confirm(second)
        self.assertEqual(Flight.objects.count(), 2)
        self.assertEqual(set(Flight.objects.values_list('registration__registration', flat=True)), {'N12345', 'N22222'})

    def test_identical_rows_are_preserved_within_a_single_batch(self):
        batch = CSVImportBatch.objects.create(user=self.user, content=content([row(), row()]), row_count=2)
        self.assertEqual(self.confirm(batch).json()['row_count'], 2)
        self.confirm(batch)
        self.assertEqual(Flight.objects.count(), 2)

    def test_notification_failure_does_not_reopen_completed_batch(self):
        with patch('csv_app.csv_import.email_confirmation', side_effect=TimeoutError('mail')) as notify:
            with self.assertLogs('django.csv_app', level='ERROR'):
                with self.captureOnCommitCallbacks(execute=True):
                    self.confirm()
            self.confirm()
        notify.assert_called_once()
        self.assertEqual(Flight.objects.count(), 1)


class CSVConcurrentConfirmationTests(TransactionTestCase):
    def test_simultaneous_confirmations_import_only_once(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Row-lock concurrency regression requires PostgreSQL.')
        user = get_user_model().objects.create_user(username='batch_concurrent')
        batch = CSVImportBatch.objects.create(user=user, content=content(), row_count=1)
        barrier = Barrier(2)
        def confirm():
            close_old_connections()
            try:
                worker_user = get_user_model().objects.get(pk=user.pk)
                barrier.wait(timeout=10)
                result, duplicate = confirm_csv_import(SimpleNamespace(user=worker_user), batch.pk)
                return result.row_count, duplicate
            finally:
                connection.close()
        with patch('csv_app.csv_import.email_confirmation') as notify:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(confirm) for _ in range(2)]
                results = [future.result(timeout=30) for future in futures]
        self.assertEqual(sorted(results), [(1, False), (1, True)])
        self.assertEqual(Flight.objects.count(), 1)
        self.assertEqual(Approach.objects.count(), 1)
        notify.assert_called_once()
