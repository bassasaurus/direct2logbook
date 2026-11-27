from decimal import Decimal
from django.test import SimpleTestCase, TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from csv_app.block_times import elapsed_hours, OvernightConfirmationRequired
from csv_app.validation import CSVValidationError, parse_csv
from csv_app.mapping import read_source, normalize_mapping, MAPPING_FIELDS
from csv_app.forms import ColumnMappingForm
from csv_app.tests.test_mapping import source_csv, choices
from csv_app.tests.airport_fixtures import seed_airports
from csv_app.tests.record_fixtures import seed_records
from flights.models import Flight


class BlockTimeTests(SimpleTestCase):
    def test_clock_difference_and_tenth_rounding(self):
        self.assertEqual(elapsed_hours('14:10','15:40'),Decimal('1.5'))
        self.assertEqual(elapsed_hours('14:00','15:03'),Decimal('1.1'))

    def test_overnight_is_not_guessed_from_clock_times(self):
        with self.assertRaises(OvernightConfirmationRequired):
            elapsed_hours('23:30','01:00')
        self.assertEqual(elapsed_hours('23:30','01:00',True),Decimal('1.5'))

    def test_dated_times_and_utc_offsets_use_actual_elapsed_time(self):
        self.assertEqual(elapsed_hours('2026-11-20 23:30','2026-11-21 01:00'),Decimal('1.5'))
        self.assertEqual(elapsed_hours('2026-11-20T23:00-06:00','2026-11-21T02:00-05:00'),Decimal('2.0'))

    def test_invalid_mixed_or_reverse_times_are_not_guessed(self):
        for out, arrival in [('25:00','26:00'),('12:00','12:00'),('12:00','2026-11-20 13:00'),
            ('2026-11-20T12:00Z','2026-11-20T13:00'),('2026-11-21 12:00','2026-11-20 13:00')]:
            with self.subTest(out=out,arrival=arrival), self.assertRaises(CSVValidationError):
                elapsed_hours(out,arrival,True)

    def test_missing_duration_is_calculated_without_dividing_clock_time_as_minutes(self):
        table=read_source(source_csv(['Date','Aircraft','Block Out','Block In'],[['2026-11-20','C172','14:10','15:40']]))
        form=ColumnMappingForm(table=table)
        self.assertEqual(form[f'map_{MAPPING_FIELDS.index("duration")}'].value(),'block_times')
        data=choices(table, registration={'value':'N12345'}, route={'value':'KIAH-KCLL'})
        data[f'map_{MAPPING_FIELDS.index("duration")}']='block_times'
        form=ColumnMappingForm(data,table=table)
        self.assertTrue(form.is_valid(),form.errors)
        rows,_=parse_csv(normalize_mapping(table,form.cleaned_data['mapping'],'minutes'))
        self.assertEqual(rows[0]['duration'],Decimal('1.5'))

    def test_matching_duration_needs_no_difference_confirmation(self):
        table=read_source(source_csv(['Date','Aircraft','Duration','Block Out','Block In'],
            [['2026-11-20','C172','01:30','14:10','15:40']]))
        form=ColumnMappingForm(choices(table),table=table)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertFalse(form.block_checks()[0]['difference'])
        self.assertFalse(form.show_time_units)

    def test_disagreement_requires_explicit_choice(self):
        table=read_source(source_csv(['Date','Aircraft','Duration','Block Out','Block In'],
            [['2026-11-20','C172','2.0','14:10','15:40']]))
        data=choices(table, registration={'value':'N12345'}, route={'value':'KIAH-KCLL'})
        form=ColumnMappingForm(data,table=table)
        self.assertFalse(form.is_valid())
        self.assertIn('confirm_block_difference',form.errors)
        data['confirm_block_difference']='on'
        form=ColumnMappingForm(data,table=table)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(parse_csv(normalize_mapping(table,form.cleaned_data['mapping']))[0][0]['duration'],Decimal('2.0'))
        # A previous acknowledgement must not be retained when selecting calculation.
        data['confirm_block_difference']='on'
        data[f'map_{MAPPING_FIELDS.index("duration")}']='block_times'
        data['ignore_unused']='on'
        form=ColumnMappingForm(data,table=table)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertFalse(form.cleaned_data['confirm_block_difference'])
        self.assertEqual(parse_csv(normalize_mapping(table,form.cleaned_data['mapping']))[0][0]['duration'],Decimal('1.5'))

    def test_plain_numeric_minutes_are_compared_in_hours(self):
        table=read_source(source_csv(['Date','Aircraft','Duration','Block Out','Block In'],
            [['2026-11-20','C172','90','14:10','15:40']]))
        form=ColumnMappingForm(dict(choices(table),time_units='minutes'),table=table)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertFalse(form.block_checks()[0]['difference'])

    def test_incomplete_pair_cannot_pass_mapping(self):
        table=read_source(source_csv(['Date','Aircraft','Duration','Block Out'],[['2026-11-20','C172','1.5','14:10']]))
        form=ColumnMappingForm(choices(table),table=table)
        self.assertFalse(form.is_valid())
        self.assertIn('Match both Block Out and Block In',str(form.errors))


@override_settings(SECURE_SSL_REDIRECT=False)
class BlockTimeWizardTests(TestCase):
    def setUp(self):
        seed_airports()
        self.user=get_user_model().objects.create_user('block-import')
        seed_records(self.user)
        self.client.force_login(self.user)

    def upload(self,records,extra_headers=None):
        text=source_csv(['Date','Aircraft','Tailnumber','Route','Block Out','Block In']+(extra_headers or []),records)
        response=self.client.post(reverse('csv_inspect'),{'file':SimpleUploadedFile('block.csv',text.encode())})
        return response.context['batch'],read_source(text)

    def test_overnight_requires_confirmation_then_previews_correct_duration(self):
        batch,table=self.upload([['2026-11-20','C172','N12345','KIAH-KCLL','23:30','01:00']])
        data=choices(table);data[f'map_{MAPPING_FIELDS.index("duration")}']='block_times'
        response=self.client.post(reverse('csv_mapping',args=[batch.pk]),data)
        self.assertContains(response,'Confirm the overnight crossing')
        self.assertFalse(Flight.objects.exists())
        data['confirm_overnight']='on'
        response=self.client.post(reverse('csv_mapping',args=[batch.pk]),data)
        self.assertTrue(response.context['preview_ready'])
        self.assertEqual(response.context['file'][0][4],'1.5')
        batch.refresh_from_db()
        self.assertTrue(batch.source_metadata['block_overnight_confirmed'])
        self.assertFalse(Flight.objects.exists())

    def test_bad_block_times_reach_duration_correction_instead_of_creating_a_flight(self):
        batch,table=self.upload([['2026-11-20','C172','N12345','KIAH-KCLL','bad','15:40']])
        data=choices(table);data[f'map_{MAPPING_FIELDS.index("duration")}']='block_times'
        response=self.client.post(reverse('csv_mapping',args=[batch.pk]),data)
        self.assertTrue(response.context['row_choice'])
        self.assertContains(response,'Duration')
        self.assertFalse(Flight.objects.exists())

    def test_difference_does_not_get_hidden_before_import(self):
        batch,table=self.upload([['2026-11-20','C172','N12345','KIAH-KCLL','14:10','15:40','2.0']],['Duration'])
        response=self.client.post(reverse('csv_mapping',args=[batch.pk]),choices(table))
        self.assertContains(response,'Duration differs')
        self.assertContains(response,'Review the differences')
        self.assertFalse(Flight.objects.exists())
