from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from csv_app.validation import HEADERS, OPTIONAL_HEADERS, CSVValidationError, parse_csv
from csv_app.mapping import read_source
from csv_app.rows import stage_rows, validate_rows
from csv_app.csv_import import csv_import, confirm_csv_import
from csv_app.tests.test_atomic_import import content, row, device_row
from csv_app.tests.test_adapters import source
from csv_app.tests.test_mapping import choices
from csv_app.tests.airport_fixtures import seed_airports
from csv_app.tests.record_fixtures import seed_records
from flights.models import Flight, Approach, Holding, Total


def typed_row(types='ILS: 1; LPV: 1', holding='Yes', **changes):
    return row(**changes) + ['', '', '', '0', '', holding, types]


class SharedCSVFieldParsingTests(SimpleTestCase):
    def test_holding_accepts_booleans_and_counts(self):
        for value, expected in [('Yes',True),('2',True),('true',True),('No',False),('0',False),('',False)]:
            with self.subTest(value=value):
                parsed,_ = parse_csv(content([typed_row(holding=value)]))
                self.assertEqual(parsed[0]['hold'], expected)
        for value in ('-1','0.5','maybe'):
            with self.subTest(value=value), self.assertRaisesRegex(CSVValidationError,'Holding:'):
                parse_csv(content([typed_row(holding=value)]))

    def test_approach_types_preserve_counts_and_do_not_invent_minima(self):
        for text,total,expected in [
            ('ILS:2; LPV:1','3',[('ILS',2),('LPV',1)]),
            ('2 ILS; VOR x1','3',[('ILS',2),('VOR',1)]),
            ('ILS CAT II','2',[('CATII',2)]),
            ('RNAV','1',[('RNAV',1)]),
            ('RNAV (GPS) — LNAV/VNAV','1',[('LNAV/VNAV',1)]),
            ('ILS; ILS','2',[('ILS',2)]),
        ]:
            with self.subTest(text=text):
                parsed,_ = parse_csv(content([typed_row(types=text,**{'10':total})]))
                self.assertEqual([(a['approach_type'],a['number']) for a in parsed[0]['approach_details']],expected)

    def test_count_only_remains_unspecified_and_type_only_supplies_count(self):
        parsed,_=parse_csv(content())
        self.assertEqual(parsed[0]['approach_details'],[{'approach_type':'','number':2}])
        parsed,_=parse_csv(content([typed_row(types='LPV:2',**{'10':''})]))
        self.assertEqual(parsed[0]['approaches'],2)

    def test_unknown_types_and_conflicting_counts_require_correction(self):
        for text in ('ILS:1; LPV:2','made up','ILS RWY 16','ILS:0'):
            with self.subTest(text=text), self.assertRaisesRegex(CSVValidationError,'Approach types:'):
                parse_csv(content([typed_row(types=text)]))

    def test_device_descriptions_and_atd_subtypes_are_normalized(self):
        for kind,code,level in [('Full Flight Simulator','FFS',''),('Flight Training Device','FTD',''),
                                ('BATD','ATD','BATD'),('AATD','ATD','AATD')]:
            with self.subTest(kind=kind):
                values=device_row(**{'5':'0','15':'1.5'})
                values[19]=kind
                parsed,preview=parse_csv(content([values]))
                self.assertEqual((parsed[0]['device_type'],parsed[0]['atd_type']),(code,level))
                self.assertEqual((preview[0][19],preview[0][21]),(code,level))

    def test_ambiguous_simulator_does_not_guess_device_category(self):
        values=device_row(**{'5':'0','15':'1.5'})
        values[19]='Simulator / FTD'
        with self.assertRaisesRegex(CSVValidationError,'Device type:'):
            parse_csv(content([values]))
        values[19]='AATD';values[21]='BATD'
        with self.assertRaisesRegex(CSVValidationError,'ATD type:'):
            parse_csv(content([values]))


@override_settings(SECURE_SSL_REDIRECT=False)
class SharedCSVFieldImportTests(TestCase):
    def setUp(self):
        seed_airports()
        self.user=get_user_model().objects.create_user('shared-csv-fields')
        self.aircraft,self.tail=seed_records(self.user)
        self.request=SimpleNamespace(user=self.user)
        self.client.force_login(self.user)

    def test_typed_approaches_and_holding_round_trip_without_loss(self):
        csv_import.run(self.request,content([typed_row()]))
        flight=Flight.objects.get(user=self.user)
        self.assertTrue(flight.hold)
        self.assertTrue(flight.holding_set.get().hold)
        self.assertEqual(set(flight.approach_set.values_list('approach_type','number')),{('ILS',1),('LPV',1)})
        exported=self.client.get(reverse('csv_download')).content.decode()
        csv_import.run(self.request,exported)
        copy=Flight.objects.exclude(pk=flight.pk).get()
        self.assertTrue(copy.hold)
        self.assertEqual(set(copy.approach_set.values_list('approach_type','number')),{('ILS',1),('LPV',1)})
        self.assertEqual(Total.objects.get(user=self.user,total='All').total_time,Decimal('3.0'))

    def test_count_only_is_displayed_as_unspecified(self):
        csv_import.run(self.request,content())
        flight=Flight.objects.get(user=self.user)
        self.assertEqual(flight.approach_set.get().approach_type,'')
        self.assertContains(self.client.get(reverse('flight_detail',args=[flight.pk])),'Unspecified-2')

    def test_bad_approach_type_is_promoted_to_an_editable_row_field(self):
        errors=validate_rows(self.user,stage_rows(content([typed_row(types='bad type')])))
        self.assertIn('approach types',errors[2])

    def test_approach_type_change_invalidates_previous_overlap_approval(self):
        from csv_app.overlaps import possible_overlaps
        raw=content([typed_row()])
        csv_import.run(self.request,raw)
        response=self.client.post(reverse('csv_inspect'),{'file':SimpleUploadedFile('overlap.csv',raw.encode())})
        batch=response.context['batch']
        issue=possible_overlaps(batch,self.user)[0]
        Approach.objects.filter(flight_object__user=self.user,approach_type='ILS').update(approach_type='LOC')
        response=self.client.post(reverse('csv_overlaps',args=[batch.pk]),{
            f'decision_{issue["line"]}':'include',f'token_{issue["line"]}':issue['token']})
        self.assertContains(response,'Matching entries changed')
        self.assertContains(response,'LOC: 1')
        self.assertEqual(Flight.objects.filter(user=self.user).count(),1)

    def test_failure_writing_second_approach_rolls_back_flight_and_holding(self):
        create=Approach.objects.create
        calls=0
        def fail(**kwargs):
            nonlocal calls
            calls+=1
            if calls==2:
                raise RuntimeError('write failed')
            return create(**kwargs)
        with patch('csv_app.csv_import.Approach.objects.create',side_effect=fail):
            with self.assertRaisesRegex(RuntimeError,'write failed'):
                csv_import.run(self.request,content([typed_row()]))
        self.assertFalse(Flight.objects.filter(user=self.user).exists())
        self.assertFalse(Approach.objects.exists())
        self.assertFalse(Holding.objects.exists())

    def test_safelog_verified_headings_map_through_wizard(self):
        headers=['Date','Aircraft Type','Aircraft Registration','Duration of Flight','Instrument Approaches',
                 'From','To','PIC','Holding','Approach Types']
        raw=source(headers,[['2026-11-20','C172','N12345','01:30','3','KIAH','KCLL','01:30','Yes','ILS:2; LPV:1']])
        table=read_source(raw)
        self.assertEqual(table.source_key,'safelog')
        response=self.client.post(reverse('csv_inspect'),{'file':SimpleUploadedFile('safelog.csv',raw.encode())})
        batch=response.context['batch']
        response=self.client.post(reverse('csv_mapping',args=[batch.pk]),dict(choices(table),ignore_unused='on'))
        self.assertTrue(response.context['preview_ready'])
        self.assertContains(response,'ILS: 2; LPV: 1')
        confirm_csv_import(self.request,batch.pk)
        flight=Flight.objects.get(user=self.user)
        self.assertEqual(flight.duration,Decimal('1.5'))
        self.assertTrue(flight.hold)
        self.assertEqual(set(flight.approach_set.values_list('approach_type','number')),{('ILS',2),('LPV',1)})
