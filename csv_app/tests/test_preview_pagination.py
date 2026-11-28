from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from csv_app.tests.airport_fixtures import seed_airports
from csv_app.tests.record_fixtures import seed_records
from csv_app.tests.test_atomic_import import content, row
from csv_app.csv_import import confirm_csv_import
from csv_app.models import CSVImportBatch
from flights.models import Flight, Total


@override_settings(SECURE_SSL_REDIRECT=False)
class PreviewPaginationTests(TestCase):
    def setUp(self):
        seed_airports()
        self.user=get_user_model().objects.create_user('preview-pages')
        seed_records(self.user)
        self.client.force_login(self.user)
        self.text=content([row(**{'18':f'Entry {index:04d}'}) for index in range(1,122)])
        response=self.client.post(reverse('csv_inspect'),{'file':SimpleUploadedFile('pages.csv',self.text.encode())})
        self.batch=response.context['batch']
        self.first=response

    def test_pages_are_bounded_but_summary_and_import_cover_entire_file(self):
        self.assertEqual(len(self.first.context['file']),50)
        self.assertEqual(self.first.context['import_summary']['flight_hours'],Decimal('181.5'))
        url=reverse('csv_preview',args=[self.batch.pk])
        second=self.client.get(url,{'page':2})
        self.assertEqual(second.context['preview_page'].number,2)
        self.assertEqual(len(second.context['file']),50)
        self.assertContains(second,'Entry 0051')
        self.assertNotContains(second,'Entry 0001')
        self.assertContains(second,'Import 121 entries')
        last=self.client.get(url,{'page':3})
        self.assertEqual(len(last.context['file']),21)
        self.assertContains(last,'Entry 0121')
        with patch('csv_app.csv_import.email_confirmation'):
            confirm_csv_import(SimpleNamespace(user=self.user),self.batch.pk)
        self.assertEqual(Flight.objects.filter(user=self.user).count(),121)
        self.assertEqual(Total.objects.get(user=self.user,total='All').total_time,Decimal('181.5'))

    def test_preview_is_owned_read_only_and_expires(self):
        url=reverse('csv_preview',args=[self.batch.pk])
        self.assertEqual(Client().get(url).status_code,302)
        other=get_user_model().objects.create_user('other-preview')
        client=Client();client.force_login(other)
        self.assertEqual(client.get(url).status_code,404)
        self.assertEqual(self.client.post(url).status_code,405)
        self.assertEqual(self.client.get(url,{'page':'bad'}).context['preview_page'].number,1)
        self.assertEqual(self.client.get(url,{'page':99999}).context['preview_page'].number,3)
        CSVImportBatch.objects.filter(pk=self.batch.pk).update(created_at=timezone.now()-timedelta(minutes=11))
        self.assertEqual(self.client.get(url).status_code,410)
        self.assertFalse(Flight.objects.exists())

    def test_submitted_and_unvalidated_batches_cannot_be_previewed(self):
        url=reverse('csv_preview',args=[self.batch.pk])
        CSVImportBatch.objects.filter(pk=self.batch.pk).update(rows_complete=False)
        self.assertRedirects(self.client.get(url),reverse('csv_rows',args=[self.batch.pk]),fetch_redirect_response=False)
        CSVImportBatch.objects.filter(pk=self.batch.pk).update(status='queued')
        self.assertEqual(self.client.get(url).status_code,409)
