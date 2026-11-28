from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from csv_app.models import CSVImportBatch
from csv_app.rows import stage_rows, validate_rows
from csv_app.tests.test_atomic_import import row, content
from csv_app.tests.record_fixtures import seed_records
from csv_app.tests.airport_fixtures import seed_airports
from csv_app.csv_import import confirm_csv_import
from csv_app.validation import CSVValidationError
from flights.models import Flight, Total, Aircraft, TailNumber


@override_settings(SECURE_SSL_REDIRECT=False)
class CSVRowCorrectionTests(TestCase):
    def test_split_pic_sic_hours_require_review_and_never_expand_silently(self):
        from decimal import Decimal
        from csv_app.validation import parse_csv
        from csv_app.csv_import import csv_import
        from home.pilot_time import source_groups
        split=row(**{'4':'2.0','5':'0.5','6':'1.5','7':'2.0'})
        with self.assertRaisesRegex(CSVValidationError, 'Partial hours need review'):
            parse_csv(content([split]))
        with self.assertRaises(CSVValidationError):
            csv_import(SimpleNamespace(user=self.user),content([row(),split]))
        self.assertFalse(Flight.objects.filter(user=self.user).exists())
        response=self.upload([split])
        self.assertTrue(response.context['row_choice'])
        fields=response.context['row_form'].row_errors[2]
        self.assertIn('pilot in command',fields)
        self.assertIn('second in command',fields)
        batch=response.context['batch']
        with self.assertRaises(CSVValidationError):
            confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)
        response=self.client.post(self.url(batch), self.post_data(batch,{(2,5):'2.0',(2,6):'0'}))
        self.assertTrue(response.context['preview_ready'])
        confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)
        total=Total.objects.get(user=self.user,total='All')
        self.assertEqual((total.total_time,total.pilot_in_command,total.second_in_command),
            (Decimal('2.0'),Decimal('2.0'),Decimal('0')))
        flights,_=source_groups(self.user)
        self.assertEqual((flights[0]['total'],flights[0]['pic'],flights[0]['sic'] or Decimal('0')),
            (Decimal('2.0'),Decimal('2.0'),Decimal('0')))

    def test_each_partial_role_is_flagged_and_legacy_flags_remain_supported(self):
        from csv_app.validation import role_hour_errors
        from csv_app.mapping import read_source, normalize_mapping
        from csv_app.tests.test_adapters import source
        from decimal import Decimal
        for index in (5,6,7,14,15,16):
            with self.subTest(column=index):
                values=row(**{'4':'2.0','5':'2.0','7':'0',str(index):'0.5'})
                self.assertTrue(role_hour_errors(values, Decimal('2.0')))
                self.assertTrue(role_hour_errors(row(**{'4':'2.0',str(index):'1.0'}), Decimal('2.0'), strict=True))
        # Generic exports with a 1.0-hour split must not be mistaken for flags.
        table=read_source(source(['Date','AircraftType','TailNumber','From','To','TotalTime','PIC','SIC'],
            [['2026-11-27','C172','N12345','IAH','CLL','2.0','1.0','1.0']]))
        self.assertTrue(table.role_times)
        normalized=normalize_mapping(table,{name:{'column':index} for name,index in table.suggestions().items()})
        data=stage_rows(normalized); data['role_times']=table.role_times
        errors=validate_rows(self.user,data)
        self.assertIn('pilot in command', errors[2])
        self.assertIn('second in command', errors[2])
        # Final validation also rechecks the source semantics, even for a stale preview.
        from csv_app.rows import validate_import_requirements
        batch=SimpleNamespace(content=normalized,source_metadata={'role_times':True})
        with self.assertRaisesRegex(CSVValidationError,'Partial hours need review'):
            validate_import_requirements(batch,self.user)

    def setUp(self):
        seed_airports()
        self.user = get_user_model().objects.create_user('row-corrections')
        seed_records(self.user)
        self.client.force_login(self.user)

    def upload(self, rows):
        return self.client.post(reverse('csv_inspect'), {'file': SimpleUploadedFile('flights.csv', content(rows).encode())})

    def url(self, batch):
        return reverse('csv_rows', args=[batch.pk])

    def post_data(self, batch, changes=None, exclude=(), page=1):
        data = {'page': page}
        for entry in batch.row_data['rows'][(page - 1)*20:page*20]:
            line = entry['line']
            if entry['excluded'] or line in exclude:
                data[f'exclude_{line}'] = 'on'
            for index, value in enumerate(entry['values']):
                data[f'row_{line}_{index}'] = (changes or {}).get((line, index), value)
        return data

    def test_multiple_bad_rows_show_fields_and_original_values_without_writes(self):
        response = self.upload([row(**{'4': 'bad', '8': '-2'}), row(**{'0': 'not-a-date', '11': '1.5'})])
        self.assertTrue(response.context['row_choice'])
        self.assertEqual(response.context['error_count'], 2)
        self.assertContains(response, 'Row 2')
        self.assertContains(response, 'Row 3')
        self.assertContains(response, 'Original: bad')
        fields = response.context['row_form'].row_errors
        self.assertIn('duration', fields[2])
        self.assertIn('night', fields[2])
        self.assertIn('date', fields[3])
        self.assertIn('day landing', fields[3])
        self.assertFalse(Flight.objects.exists())

    def test_fix_values_then_import_and_verify_totals(self):
        response = self.upload([row(**{'4': 'bad', '5': '1', '7': '1'})])
        batch = response.context['batch']
        response = self.client.post(self.url(batch), self.post_data(batch, {(2, 4): '02:30'}))
        self.assertTrue(response.context['preview_ready'])
        batch.refresh_from_db()
        self.assertTrue(batch.rows_complete)
        self.assertEqual(batch.row_data['rows'][0]['original'][4], 'bad')
        confirm_csv_import(SimpleNamespace(user=self.user), batch.pk)
        self.assertEqual(str(Flight.objects.get().duration), '2.5')
        self.assertEqual(str(Total.objects.get(user=self.user, total='All').total_time), '2.5')

    def test_exclude_invalid_row_imports_only_included_and_reports_count(self):
        batch = self.upload([row(), row(**{'4': 'bad'})]).context['batch']
        response = self.client.post(self.url(batch), self.post_data(batch, exclude=[3]))
        self.assertTrue(response.context['preview_ready'])
        self.assertEqual(response.context['excluded_count'], 1)
        self.assertContains(response, '1 row excluded')
        batch.refresh_from_db()
        self.assertEqual(batch.row_count, 1)
        confirm_csv_import(SimpleNamespace(user=self.user), batch.pk)
        self.assertEqual(Flight.objects.count(), 1)

    def test_all_excluded_cannot_import(self):
        batch = self.upload([row(**{'4': 'bad'})]).context['batch']
        response = self.client.post(self.url(batch), self.post_data(batch, exclude=[2]))
        self.assertContains(response, 'Include at least one flight')
        self.assertEqual(self.client.post(reverse('csv_upload'), {'batch_id': batch.pk}).status_code, 400)
        self.assertFalse(Flight.objects.exists())

    def test_invalid_correction_remains_blocked_and_preserves_original(self):
        batch = self.upload([row(**{'4': 'bad'})]).context['batch']
        response = self.client.post(self.url(batch), self.post_data(batch, {(2, 4): '-1'}))
        self.assertTrue(response.context['row_choice'])
        batch.refresh_from_db()
        self.assertFalse(batch.rows_complete)
        self.assertEqual(batch.row_data['rows'][0]['values'][4], '-1')
        self.assertEqual(batch.row_data['rows'][0]['original'][4], 'bad')
        with patch('csv_app.submission.import_csv_batch.apply_async') as task:
            self.assertEqual(self.client.post(reverse('csv_upload'), {'batch_id': batch.pk}).status_code, 400)
            task.assert_not_called()
        with self.assertRaisesRegex(CSVValidationError, 'Correct or exclude'):
            confirm_csv_import(SimpleNamespace(user=self.user), batch.pk)

    def test_editing_good_preview_reopens_validation_and_matching(self):
        batch = self.upload([row()]).context['batch']
        response = self.client.get(self.url(batch))
        self.assertTrue(response.context['row_choice'])
        batch.refresh_from_db()
        self.assertFalse(batch.records_complete)
        self.assertFalse(batch.rows_complete)
        response = self.client.post(self.url(batch), self.post_data(batch, {(2, 2): 'N77777'}))
        self.assertTrue(response.context['record_choice'])
        self.assertFalse(response.context['batch'].records_complete)

    def test_unknown_route_can_be_corrected(self):
        batch = self.upload([row(**{'3': 'KIAH-ZZZZ'})]).context['batch']
        response = self.client.get(self.url(batch))
        self.assertContains(response, 'Airport not found: ZZZZ')
        response = self.client.post(self.url(batch), self.post_data(batch, {(2, 3): 'IAH-CLL'}))
        self.assertTrue(response.context['preview_ready'])
        self.assertContains(response, 'KIAH-KCLL')

    def test_blank_source_lines_keep_original_numbers(self):
        response = self.upload([[], row(), [], row(**{'4': 'bad'})])
        self.assertEqual([entry['line'] for entry in response.context['correction_rows']], [3, 5])
        self.assertIn(5, response.context['row_form'].row_errors)

    def test_excluded_row_can_be_included_again_after_fix(self):
        batch = self.upload([row(), row(**{'4': 'bad', '5': '1', '7': '1'})]).context['batch']
        self.client.post(self.url(batch), self.post_data(batch, exclude=[3]))
        batch.refresh_from_db()
        self.client.get(self.url(batch))
        data = self.post_data(batch, {(3, 4): '1.0'})
        data.pop('exclude_3')
        response = self.client.post(self.url(batch), data)
        self.assertTrue(response.context['preview_ready'])
        self.assertEqual(response.context['excluded_count'], 0)
        self.assertEqual(response.context['row_count'], 2)

    def test_ambiguous_dates_still_require_choice_after_correction(self):
        batch = self.upload([row(**{'0': '05/06/2026', '4': 'bad', '5': '1', '7': '1'})]).context['batch']
        response = self.client.post(self.url(batch), self.post_data(batch, {(2, 4): '1.0'}))
        self.assertTrue(response.context['date_choice'])
        self.assertFalse(Flight.objects.exists())

    def test_pagination_saves_page_edits_without_losing_other_rows(self):
        batch = self.upload([row(**{'4': 'bad'}) for _ in range(21)]).context['batch']
        data = self.post_data(batch, {(2, 4): '1.0'})
        data['show_page'] = '2'
        response = self.client.post(self.url(batch), data)
        self.assertEqual(len(response.context['correction_rows']), 1)
        batch.refresh_from_db()
        self.assertEqual(batch.row_data['rows'][0]['values'][4], '1.0')
        self.assertEqual(batch.row_data['rows'][20]['values'][4], 'bad')

    def test_owner_csrf_expiry_and_submitted_guards(self):
        batch = self.upload([row(**{'4': 'bad'})]).context['batch']
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.url(batch), {}).status_code, 403)
        other = get_user_model().objects.create_user('other-rows')
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.url(batch)).status_code, 404)
        self.client.force_login(self.user)
        batch.status = 'queued'
        batch.save()
        self.assertEqual(self.client.get(self.url(batch)).status_code, 409)
        batch.status = 'preview'
        batch.save()
        CSVImportBatch.objects.filter(pk=batch.pk).update(created_at=timezone.now() - timedelta(minutes=11))
        self.assertEqual(self.client.get(self.url(batch)).status_code, 410)


    def test_required_text_fields_highlight_the_correct_fields(self):
        response = self.upload([row(**{'1': '', '2': '', '3': '', '18': 'x' * 501})])
        self.assertEqual(set(response.context['row_form'].row_errors[2]), {'aircraft', 'registration', 'route', 'remarks'})

    def test_correction_data_is_erased_after_completion_and_expiry(self):
        from django.core.management import call_command
        from io import StringIO
        batch = self.upload([row()]).context['batch']
        confirm_csv_import(SimpleNamespace(user=self.user), batch.pk)
        batch.refresh_from_db()
        self.assertEqual(batch.row_data, {})
        batch = self.upload([row(**{'4': 'bad'})]).context['batch']
        CSVImportBatch.objects.filter(pk=batch.pk).update(created_at=timezone.now() - timedelta(minutes=11))
        call_command('cleanup_csv_previews', stdout=StringIO())
        batch.refresh_from_db()
        self.assertEqual(batch.row_data, {})

    def test_known_date_order_is_kept_after_editing(self):
        response = self.upload([row(**{'0': '25/06/2026'})])
        batch = response.context['batch']
        self.client.get(self.url(batch))
        batch.refresh_from_db()
        response = self.client.post(self.url(batch), self.post_data(batch, {(2, 0): '05/06/2026'}))
        self.assertTrue(response.context['preview_ready'])
        batch.refresh_from_db()
        self.assertIn('2026-06-05', batch.content)

    def test_missing_duration_stays_in_corrections_and_cannot_be_queued_or_imported(self):
        from csv_app.submission import queue_csv_import
        response = self.upload([row(**{'4': ''})])
        self.assertTrue(response.context['row_choice'])
        batch = response.context['batch']
        self.assertFalse(batch.rows_complete)
        self.assertContains(response, 'Duration is required.')
        # Completion flags alone cannot bypass validation of the saved CSV.
        batch.rows_complete = True
        batch.records_complete = True
        batch.date_order = 'unambiguous'
        batch.save()
        with patch('csv_app.submission.import_csv_batch.apply_async') as task:
            with self.assertRaisesRegex(CSVValidationError, 'Duration is required'):
                queue_csv_import(self.user, batch.pk)
            task.assert_not_called()
        with self.assertRaisesRegex(CSVValidationError, 'Duration is required'):
            confirm_csv_import(SimpleNamespace(user=self.user), batch.pk)
        self.assertFalse(Flight.objects.exists())

    def test_missing_actual_route_or_tail_cannot_bypass_import_validation(self):
        from csv_app.submission import queue_csv_import
        for field in ('2', '3'):
            with self.subTest(field=field):
                batch = CSVImportBatch.objects.create(user=self.user, content=content([row(**{field: ''})]),
                    row_count=1, mapping_complete=True, rows_complete=True, records_complete=True, date_order='unambiguous')
                with patch('csv_app.submission.import_csv_batch.apply_async') as task:
                    with self.assertRaises(CSVValidationError):
                        queue_csv_import(self.user, batch.pk)
                    task.assert_not_called()
                with self.assertRaises(CSVValidationError):
                    confirm_csv_import(SimpleNamespace(user=self.user), batch.pk)
        self.assertFalse(Flight.objects.exists())


class ImportedRecordChoiceTests(TestCase):
    def test_choices_use_file_aircraft_and_their_registrations_without_account_records(self):
        from django import forms
        from csv_app.forms import RowCorrectionForm
        data = stage_rows(content([row(**{'1': 'DA40NG', '2': 'N400TS'}),
                                   row(**{'1': 'B190', '2': 'N190TS'})]))
        form = RowCorrectionForm(data_rows=data)
        self.assertIsInstance(form.fields['row_2_1'].widget, forms.Select)
        self.assertEqual(form.aircraft_options, ['DA40NG', 'B190'])
        self.assertIn(('N400TS', 'N400TS'), list(form.fields['row_2_2'].widget.choices))
        self.assertNotIn(('N190TS', 'N190TS'), list(form.fields['row_2_2'].widget.choices))
        self.assertFalse(Aircraft.objects.exists())
        self.assertFalse(TailNumber.objects.exists())

    def test_raw_file_choices_survive_blank_mapping_and_allow_explicit_correction(self):
        from csv_app.forms import RowCorrectionForm
        data = stage_rows(content([row(**{'1': '', '2': 'N400TS'})]))
        data['record_choices'] = {'aircraft': ['DA40NG', 'B190'],
            'tailnumbers': {'da40ng': ['N400TS'], 'b190': ['N190TS']}}
        form = RowCorrectionForm(data_rows=data)
        self.assertEqual(form.aircraft_options, ['DA40NG', 'B190'])
        posted = {f'row_2_{index}': value for index, value in enumerate(data['rows'][0]['values'])}
        posted.update(row_2_1='__custom__', custom_row_2_1='PA28', row_2_2='__custom__', custom_row_2_2='N281AA')
        edited = RowCorrectionForm(posted, data_rows=data)
        self.assertTrue(edited.is_valid(), edited.errors)
        self.assertEqual(edited.corrected()['rows'][0]['values'][1:3], ['PA28', 'N281AA'])
