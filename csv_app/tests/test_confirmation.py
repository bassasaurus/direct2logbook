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
        self.batch = CSVImportBatch.objects.create(user=self.user, content=content(), row_count=1)
        self.request = SimpleNamespace(user=self.user)

    def test_repeat_confirmation_returns_receipt_without_more_flights_or_emails(self):
        with patch('csv_app.csv_import.email_confirmation') as notify:
            with self.captureOnCommitCallbacks(execute=True):
                result, first_duplicate = confirm_csv_import(self.request, self.batch.pk)
                result, second_duplicate = confirm_csv_import(self.request, self.batch.pk)
        self.assertFalse(first_duplicate)
        self.assertTrue(second_duplicate)
        self.assertEqual(Flight.objects.count(), 1)
        notify.assert_called_once()
        result.refresh_from_db()
        self.assertTrue(result.completed)
        self.assertEqual(result.content, '')

    def test_write_failure_rolls_back_completion_and_remains_retryable(self):
        with patch('csv_app.csv_import.Approach.objects.create', side_effect=RuntimeError('write failed')):
            with self.assertRaises(RuntimeError):
                confirm_csv_import(self.request, self.batch.pk)
        self.batch.refresh_from_db()
        self.assertFalse(self.batch.completed)
        self.assertTrue(self.batch.content)
        self.assertFalse(Flight.objects.exists())
        confirm_csv_import(self.request, self.batch.pk)
        self.assertEqual(Flight.objects.count(), 1)

    def test_identical_flights_in_one_batch_are_preserved(self):
        self.batch.content = content([row(), row()])
        self.batch.save()
        confirm_csv_import(self.request, self.batch.pk)
        confirm_csv_import(self.request, self.batch.pk)
        self.assertEqual(Flight.objects.count(), 2)


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
