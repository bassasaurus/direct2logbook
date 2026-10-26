from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from csv_app.models import CSVImportBatch
from csv_app.tests.test_atomic_import import content
from flights.models import Flight


@override_settings(SECURE_SSL_REDIRECT=False)
class CSVPreviewExpiryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='csv_expiry')
        self.client.force_login(self.user)

    def batch(self, age=11, completed=False):
        batch = CSVImportBatch.objects.create(
            user=self.user, content='' if completed else content(), row_count=1,
            completed=completed, completed_at=timezone.now() if completed else None,
        )
        CSVImportBatch.objects.filter(pk=batch.pk).update(created_at=timezone.now() - timedelta(minutes=age))
        batch.refresh_from_db()
        return batch

    def cleanup(self, dry_run=False):
        output = StringIO()
        call_command('cleanup_csv_previews', dry_run=dry_run, stdout=output)
        return output.getvalue()

    def test_expired_preview_is_rejected_even_before_cleanup_runs(self):
        batch = self.batch()
        response = self.client.post(reverse('csv_upload'), {'batch_id': batch.pk})
        self.assertEqual(response.status_code, 410)
        self.assertIn('Upload and inspect', response.json()['message'])
        self.assertFalse(Flight.objects.exists())

    def test_cleanup_removes_only_expired_pending_content(self):
        expired = self.batch()
        fresh = self.batch(age=1)
        completed = self.batch(completed=True)
        receipt_time = completed.completed_at
        self.assertIn('Cleared 1', self.cleanup())
        expired.refresh_from_db()
        fresh.refresh_from_db()
        completed.refresh_from_db()
        self.assertEqual(expired.content, '')
        self.assertTrue(fresh.content)
        self.assertTrue(completed.completed)
        self.assertEqual(completed.completed_at, receipt_time)
        self.assertEqual(CSVImportBatch.objects.count(), 3)

    def test_cleanup_dry_run_and_repetition(self):
        batch = self.batch()
        self.assertIn('payloads: 1', self.cleanup(dry_run=True))
        batch.refresh_from_db()
        self.assertTrue(batch.content)
        self.cleanup()
        self.assertIn('Cleared 0', self.cleanup())

    def test_cleared_preview_token_remains_expired(self):
        batch = self.batch()
        self.cleanup()
        self.assertEqual(self.client.post(reverse('csv_upload'), {'batch_id': batch.pk}).status_code, 410)
        self.assertFalse(Flight.objects.exists())

    @patch('csv_app.csv_import.csv_import')
    def test_old_completed_receipt_still_blocks_reimport(self, importer):
        batch = self.batch(age=100, completed=True)
        self.cleanup()
        response = self.client.post(reverse('csv_upload'), {'batch_id': batch.pk})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['already_completed'])
        importer.assert_not_called()

    def test_another_user_cannot_check_an_expired_token(self):
        batch = self.batch()
        other = get_user_model().objects.create_user(username='csv_expiry_other')
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse('csv_upload'), {'batch_id': batch.pk}).status_code, 404)

    def test_expiry_boundary_is_exact(self):
        batch = self.batch(age=1)
        with patch('csv_app.models.timezone.now', return_value=batch.expires_at - timedelta(microseconds=1)):
            self.assertFalse(batch.is_expired)
        with patch('csv_app.models.timezone.now', return_value=batch.expires_at):
            self.assertTrue(batch.is_expired)
