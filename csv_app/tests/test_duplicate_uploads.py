from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from csv_app.models import CSVImportBatch
from csv_app.duplicates import upload_digest
from csv_app.submission import queue_csv_import
from csv_app.csv_import import confirm_csv_import
from csv_app.tests.test_atomic_import import content
from csv_app.tests.airport_fixtures import seed_airports
from csv_app.tests.record_fixtures import seed_records
from flights.models import Flight


@override_settings(SECURE_SSL_REDIRECT=False)
class DuplicateUploadTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('duplicate-uploads')
        self.client.force_login(self.user)
        seed_airports()
        seed_records(self.user)

    def upload(self, name='test.csv', text=None):
        return self.client.post(reverse('csv_inspect'), {'file': SimpleUploadedFile(name,(text or content()).encode())})

    def test_digest_ignores_filename_bom_and_line_endings(self):
        self.assertEqual(upload_digest(content()), upload_digest('\ufeff'+content().replace('\r\n','\n')+'\n'))
        self.assertNotEqual(upload_digest(content()), upload_digest(content().replace('1.5','1.6')))

    def test_completed_reupload_returns_receipt_without_another_batch_or_flight(self):
        batch=self.upload().context['batch']
        confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)
        response=self.upload('renamed.csv','\ufeff'+content().replace('\r\n','\n'))
        self.assertContains(response,'This file has already been imported. No flights were added.')
        self.assertEqual(response.context['latest_import'].pk,batch.pk)
        self.assertEqual(CSVImportBatch.objects.count(),1)
        self.assertEqual(Flight.objects.count(),1)
        self.assertNotContains(response,'Import 1 flight')

    @patch('csv_app.submission.import_csv_batch.apply_async')
    def test_two_previews_can_only_queue_one_import(self, publish):
        one=self.upload().context['batch']
        two=self.upload().context['batch']
        original, duplicate=queue_csv_import(self.user,one.pk)
        reused, duplicate=queue_csv_import(self.user,two.pk)
        self.assertTrue(duplicate)
        self.assertEqual(original.pk,reused.pk)
        publish.assert_called_once()
        response=self.upload()
        self.assertContains(response,'This file is already being imported.')

    @patch('csv_app.submission.import_csv_batch.apply_async')
    def test_database_enforces_single_submitted_fingerprint(self, publish):
        one=self.upload().context['batch']
        two=self.upload().context['batch']
        queue_csv_import(self.user,one.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CSVImportBatch.objects.filter(pk=two.pk).update(status='queued')

    def test_worker_confirmation_also_reuses_another_completed_copy(self):
        one=self.upload().context['batch']
        two=self.upload().context['batch']
        confirm_csv_import(SimpleNamespace(user=self.user),one.pk)
        receipt, duplicate=confirm_csv_import(SimpleNamespace(user=self.user),two.pk)
        self.assertTrue(duplicate)
        self.assertEqual(receipt.pk,one.pk)
        self.assertEqual(Flight.objects.count(),1)

    def test_other_account_is_not_blocked_or_exposed(self):
        batch=self.upload().context['batch']
        confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)
        other=get_user_model().objects.create_user('other-importer')
        seed_records(other)
        self.client.force_login(other)
        response=self.upload()
        self.assertTrue(response.context['preview_ready'])
        self.assertNotContains(response,'already been imported')

    @patch('csv_app.submission.import_csv_batch.apply_async')
    def test_failed_import_may_retry_same_file(self, publish):
        old=self.upload().context['batch']
        CSVImportBatch.objects.filter(pk=old.pk).update(status='failed',content='')
        new=self.upload().context['batch']
        queued, duplicate=queue_csv_import(self.user,new.pk)
        self.assertFalse(duplicate)
        self.assertEqual(queued.pk,new.pk)
        publish.assert_called_once()
