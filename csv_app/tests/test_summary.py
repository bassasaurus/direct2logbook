from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from csv_app.models import CSVImportBatch
from csv_app.summary import import_summary
from csv_app.csv_import import confirm_csv_import
from csv_app.tests.test_atomic_import import content, row, device_row
from csv_app.tests.record_fixtures import seed_records
from csv_app.tests.airport_fixtures import seed_airports
from flights.models import Flight, Total


@override_settings(SECURE_SSL_REDIRECT=False)
class ImportSummaryTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('import-summary')
        seed_records(self.user)
        seed_airports()
        self.client.force_login(self.user)

    def upload(self, rows):
        return self.client.post(reverse('csv_inspect'), {'file':SimpleUploadedFile('summary.csv',content(rows).encode())})

    def test_summary_separates_devices_and_uses_included_date_range(self):
        response=self.upload([
            row(**{'0':'2026-11-20','4':'1.24','5':'1','7':'1'}),
            row(**{'0':'2026-11-22','4':'2.56','5':'1','7':'1'}),
            device_row(**{'0':'2026-11-21','4':'4.0','5':'0','17':'4.0'}),
        ])
        self.assertTrue(response.context['preview_ready'])
        summary=response.context['import_summary']
        self.assertEqual((summary['entry_count'],summary['flight_count'],summary['device_count']),(3,2,1))
        self.assertEqual(summary['flight_hours'],Decimal('3.8'))
        self.assertEqual(response.context['file'][0][4],'1.2')
        self.assertEqual(response.context['file'][1][4],'2.6')
        self.assertEqual(summary['device_hours'],Decimal('4.0'))
        self.assertEqual((summary['date_start'],summary['date_end']),(date(2026,11,20),date(2026,11,22)))
        self.assertEqual(summary['edited_count'],0)  # Automatic normalization is not a user edit.
        self.assertContains(response,'Simulator / device hours')
        self.assertContains(response,'Import 3 entries')
        self.assertFalse(Flight.objects.exists())
        confirm_csv_import(SimpleNamespace(user=self.user),response.context['batch'].pk)
        totals=Total.objects.get(user=self.user,total='All')
        self.assertEqual(totals.total_time,summary['flight_hours'])
        self.assertEqual(totals.simulator,summary['device_hours'])
        self.assertEqual(Flight.objects.filter(simulator=False).count(),summary['flight_count'])
        self.assertEqual(Flight.objects.filter(simulator=True).count(),summary['device_count'])

    def test_corrected_and_excluded_rows_change_the_summary_and_imported_totals(self):
        response=self.upload([row(**{'0':'2026-11-20','4':'bad','5':'1','7':'1'}),row(**{'0':'1999-01-01','4':'bad'})])
        batch=response.context['batch']
        from csv_app.tests.test_row_corrections import CSVRowCorrectionTests
        data=CSVRowCorrectionTests.post_data(self,batch,{(2,4):'02:30'},exclude=[3])
        response=self.client.post(reverse('csv_rows',args=[batch.pk]),data)
        self.assertTrue(response.context['preview_ready'])
        summary=response.context['import_summary']
        self.assertEqual((summary['entry_count'],summary['edited_count'],summary['excluded_count']),(1,1,1))
        self.assertEqual(summary['flight_hours'],Decimal('2.5'))
        self.assertIn('Duration: HH:MM → decimal hours (nearest tenth)',summary['warnings'])
        self.assertEqual(summary['date_start'],date(2026,11,20))
        self.assertEqual(summary['date_end'],date(2026,11,20))
        self.assertEqual(summary['edited_rows'],[{'line':2,'fields':['Duration']}])
        self.assertContains(response,'Row 2 edited: Duration')
        self.assertContains(response,'Excluded rows: 3')
        confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)
        self.assertEqual(Flight.objects.count(),1)
        self.assertEqual(Total.objects.get(user=self.user,total='All').total_time,summary['flight_hours'])
        self.assertEqual(sum(Flight.objects.values_list('duration',flat=True)),summary['flight_hours'])

    def test_devices_only_summary_has_zero_flight_hours(self):
        response=self.upload([device_row(**{'4':'4','5':'0','17':'4'})])
        summary=response.context['import_summary']
        self.assertEqual(summary['flight_count'],0)
        self.assertEqual(summary['flight_hours'],Decimal('0.0'))
        self.assertEqual(summary['device_hours'],Decimal('4.0'))

    def test_actual_conversions_are_reported_and_unused_approach_warning_is_omitted(self):
        response=self.upload([row(**{'4':'01:30','10':'0','3':'IAH-CLL'})])
        warnings=response.context['preview_warnings']
        self.assertIn('Duration: HH:MM → decimal hours (nearest tenth); 01:30 → 1.5 h',warnings)
        self.assertIn('Route airport codes normalized.',warnings)
        self.assertFalse(any('ILS' in warning for warning in warnings))
        self.assertEqual(response.context['import_summary']['edited_count'],0)

    def test_review_recomputes_from_current_payload_not_cached_numbers(self):
        batch=self.upload([row()]).context['batch']
        first=import_summary(batch)
        batch.content=content([row(**{'4':'2.4','5':'2.4','7':'2.4','0':'2026-11-01'})])
        second=import_summary(batch)
        self.assertEqual(first['flight_hours'],Decimal('1.5'))
        self.assertEqual(second['flight_hours'],Decimal('2.4'))
        self.assertEqual(second['date_start'],date(2026,11,1))
