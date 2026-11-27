from csv_app.tests.record_fixtures import seed_records
import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from csv_app.csv_import import confirm_csv_import
from csv_app.forms import ColumnMappingForm
from csv_app.mapping import MAPPING_FIELDS, normalize_mapping, read_source
from csv_app.models import CSVImportBatch
from csv_app.tests.test_atomic_import import content, row
from csv_app.validation import CSVValidationError, parse_csv
from flights.models import Flight
from csv_app.tests.airport_fixtures import seed_airports


def source_csv(headers=None, records=None):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(headers or ['FlightDate', 'AircraftType', 'TailNumber', 'From', 'To', 'TotalTime', 'PIC', 'DayLandings'])
    writer.writerows(records or [['25/06/2026', 'C172', 'N12345', 'KIAH', 'KCLL', '01:30', 'true', '1']])
    return stream.getvalue()


def choices(table, **overrides):
    suggested = table.suggestions()
    data = {f'map_{index}': str(suggested[name]) if name in suggested else ''
            for index, name in enumerate(MAPPING_FIELDS)}
    # Supply valid shared flight requirements when a focused test omits those
    # columns. Tests for missing requirements submit the unmodified mappings.
    candidates = table.candidates()
    if not candidates.get('registration'):
        data['map_2'] = 'constant'
        data['value_2'] = 'N12345'
    if 'route' not in suggested:
        if 'departure' in suggested and 'destination' in suggested:
            data['map_3'] = 'airports'
        elif not candidates.get('route'):
            data['map_3'] = 'constant'
            data['value_3'] = 'KIAH-KCLL'
    if not any(candidates.get(name) for name in ('pilot in command', 'second in command', 'solo', 'dual')):
        data['map_5'] = 'constant'
        data['value_5'] = 'yes'
    for name, value in overrides.items():
        index = MAPPING_FIELDS.index(name)
        if isinstance(value, dict):
            data[f'map_{index}'] = 'constant'
            data[f'value_{index}'] = value['value']
        else:
            data[f'map_{index}'] = str(value)
    return data


class ColumnMatchingTests(SimpleTestCase):
    def test_clear_aliases_are_matched_without_guessing_vague_headings(self):
        table = read_source(source_csv())
        self.assertEqual(table.suggestions(), {'date': 0, 'aircraft': 1, 'registration': 2,
            'departure': 3, 'destination': 4, 'duration': 5, 'pilot in command': 6, 'day landing': 7})
        vague = read_source(source_csv(['When', 'Plane', 'Time'], [['2026-11-26', 'C172', '1.5']]))
        self.assertEqual(vague.suggestions(), {})

    def test_duplicate_candidates_stay_unselected_and_can_be_chosen_by_index(self):
        table = read_source(source_csv(['Date', 'Aircraft', 'Duration', 'PIC', 'Pilot in Command'],
                                       [['2026-11-26', 'C172', '1.5', '0', '1.5']]))
        self.assertNotIn('pilot in command', table.suggestions())
        data = choices(table, **{'pilot in command': '4'})
        data['ignore_unused'] = 'on'
        form = ColumnMappingForm(data, table=table)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['mapping']['pilot in command'], {'column': 4})

    def test_unmatched_data_requires_explicit_ignore_but_blank_columns_do_not(self):
        for value, valid in [('Do not lose this', False), ('', True)]:
            table = read_source(source_csv(['Date', 'Aircraft', 'Duration', 'Extra'], [['2026-11-26', 'C172', '1.5', value]]))
            data = choices(table)
            form = ColumnMappingForm(data, table=table)
            self.assertEqual(form.is_valid(), valid, form.errors)
            if not valid:
                self.assertIn('ignore_unused', form.errors)
                data['ignore_unused'] = 'on'
                self.assertTrue(ColumnMappingForm(data, table=table).is_valid())

    def test_shared_values_can_supply_missing_fields(self):
        table = read_source(source_csv(['Date', 'Duration'], [['2026-11-26', '01:30']]))
        data = choices(table, aircraft={'value': 'C172'}, registration={'value': 'N12345'},
                       route={'value': 'KIAH-KCLL'}, **{'pilot in command': {'value': 'yes'}})
        form = ColumnMappingForm(data, table=table)
        self.assertTrue(form.is_valid(), form.errors)
        parsed, _ = parse_csv(normalize_mapping(table, form.cleaned_data['mapping']))
        self.assertEqual(parsed[0]['aircraft'], 'C172')
        self.assertEqual(parsed[0]['duration'], Decimal('1.5'))
        self.assertTrue(parsed[0]['pilot_in_command'])

    def test_required_fields_and_empty_constants_cannot_be_skipped(self):
        table = read_source(source_csv(['Date', 'Duration'], [['2026-11-26', '1.5']]))
        form = ColumnMappingForm(choices(table), table=table)
        self.assertFalse(form.is_valid())
        self.assertIn('map_1', form.errors)
        form = ColumnMappingForm(choices(table, aircraft={'value': ''}), table=table)
        self.assertFalse(form.is_valid())
        self.assertIn('value_1', form.errors)

    def test_route_is_built_from_airports_and_selection_values_are_converted(self):
        table = read_source(source_csv())
        form = ColumnMappingForm(choices(table), table=table)
        self.assertTrue(form.is_valid(), form.errors)
        canonical = normalize_mapping(table, form.cleaned_data['mapping'])
        from csv_app.dates import interpret_dates
        parsed, _ = parse_csv(interpret_dates(canonical)[0])
        self.assertEqual(parsed[0]['route'], 'KIAH-KCLL')
        self.assertEqual(parsed[0]['duration'], Decimal('1.5'))
        self.assertTrue(parsed[0]['pilot_in_command'])
        self.assertEqual(parsed[0]['landings_day'], 1)

    def test_route_and_airport_mappings_cannot_silently_override_each_other(self):
        table = read_source(source_csv())
        data = choices(table, route={'value': 'KSEA-KPDX'})
        form = ColumnMappingForm(data, table=table)
        self.assertFalse(form.is_valid())
        self.assertIn('Choose Route or', str(form.non_field_errors()))

    def test_malformed_files_and_invalid_hour_minutes_are_rejected(self):
        for text in ['A,B\nonly-one', 'A\n"unclosed', source_csv(['A'] * 101, [['x'] * 101])]:
            with self.subTest(text=text[:30]), self.assertRaises(CSVValidationError):
                read_source(text)
        table = read_source(source_csv(records=[['2026-11-26', 'C172', 'N12345', 'KIAH', 'KCLL', '01:99', 'true', '1']]))
        form = ColumnMappingForm(choices(table), table=table)
        self.assertTrue(form.is_valid(), form.errors)
        normalized = normalize_mapping(table, form.cleaned_data['mapping'])
        self.assertIn('01:99', normalized)  # Retained for the row correction step.

    def test_known_format_also_converts_hours_minutes_without_mapping(self):
        from csv_app.formats import prepare_csv
        _, canonical = prepare_csv(content([row(**{'4': '01:30', '5': 'true'})]))
        parsed, _ = parse_csv(canonical)
        self.assertEqual(parsed[0]['duration'], Decimal('1.5'))
        self.assertTrue(parsed[0]['pilot_in_command'])


@override_settings(SECURE_SSL_REDIRECT=False)
class ColumnMappingWizardTests(TestCase):
    def setUp(self):
        seed_airports()
        self.user = get_user_model().objects.create_user('column-mapping')
        seed_records(self.user)
        self.client.force_login(self.user)

    def pending_batch(self, text=None):
        text = text or source_csv()
        response = self.client.post(reverse('csv_inspect'), {'file': SimpleUploadedFile('export.csv', text.encode())})
        self.assertTrue(response.context['mapping_choice'])
        self.assertFalse(Flight.objects.exists())
        return response.context['batch'], read_source(text)

    def test_mapping_keeps_all_destination_fields_in_one_card(self):
        batch, _ = self.pending_batch()
        response = self.client.get(reverse('csv_mapping', args=[batch.pk]))
        self.assertEqual([row['label'] for row in response.context['required_mapping_rows']], ['Date', 'Aircraft Type', 'Tailnumber', 'Route', 'Duration'])
        self.assertIn('Tailnumber', [row['label'] for row in response.context['required_mapping_rows']])
        self.assertIn('Night', [row['label'] for row in response.context['extra_mapping_rows']])
        self.assertNotIn('Departure Airport', [row['label'] for row in response.context['extra_mapping_rows']])
        self.assertNotContains(response, 'data-optional-mappings')
        self.assertEqual(len(response.context['mapping_rows']), len(MAPPING_FIELDS) - 4)
        self.assertEqual([row['target'] for row in response.context['conversion_mapping_rows']], ['departure', 'destination', 'block out', 'block in'])
        self.assertNotIn('departure', [row['target'] for row in response.context['mapping_rows']])
        self.assertContains(response, 'draggable="true"')
        self.assertContains(response, 'Dropdowns can reuse a column.')
        self.assertContains(response, 'card csv-mapping-fields')
        self.assertContains(response, 'data-assigned-column')
        html = response.content.decode()
        self.assertNotIn('Required fields', html)
        self.assertNotIn('Matched fields', html)
        self.assertNotIn('Other fields (', html)

    def test_ambiguous_optional_match_stays_visible_for_review(self):
        batch, _ = self.pending_batch(source_csv(['Date', 'Aircraft', 'Duration', 'PIC', 'Pilot in Command'],
            [['2026-11-20', 'C172', '1.5', '1.5', '0.5']]))
        response = self.client.get(reverse('csv_mapping', args=[batch.pk]))
        self.assertEqual([row['label'] for row in response.context['review_mapping_rows']], ['PIC'])
        self.assertNotIn('PIC', [row['label'] for row in response.context['extra_mapping_rows']])
        self.assertContains(response, 'Choose between columns')

    def test_optional_shared_value_error_cannot_hide_in_collapsed_fields(self):
        batch, table = self.pending_batch()
        data = choices(table, night={'value': ''})
        response = self.client.post(reverse('csv_mapping', args=[batch.pk]), data)
        self.assertIn('Night', [row['label'] for row in response.context['review_mapping_rows']])
        self.assertNotIn('Night', [row['label'] for row in response.context['extra_mapping_rows']])
        self.assertContains(response, 'Enter the value to use for every row.')

    def test_usage_identifies_the_exact_pic_source_before_javascript_runs(self):
        batch, table = self.pending_batch(source_csv(['Date', 'Aircraft', 'Duration', 'PIC', 'Pilot in Command'],
            [['2026-11-20', 'C172', '1.5', '0.5', '1.5']]))
        data = choices(table, **{'pilot in command': '3'})
        form = ColumnMappingForm(data, table=table)
        sources = {column['index']: column for column in form.source_columns()}
        self.assertEqual(sources[3]['usage'], 'PIC')
        self.assertTrue(sources[3]['used'])
        self.assertFalse(sources[4]['used'])
        self.assertEqual(sources[4]['possible'], 'PIC')
        self.assertIn(4, [column['index'] for column in form.unused_columns()])
        self.assertNotIn(3, [column['index'] for column in form.unused_columns()])
        response = self.client.post(reverse('csv_mapping', args=[batch.pk]), data)
        self.assertContains(response, 'Used → PIC')
        self.assertContains(response, 'Column 5 — Pilot in Command')
        self.assertContains(response, 'Your File')
        self.assertContains(response, 'Direct2Logbook')

    def test_conversion_notes_explain_route_and_time_units(self):
        table = read_source(source_csv())
        form = ColumnMappingForm(table=table)
        rows = {row['label']: row for row in form.rows()}
        self.assertIn('Departure + Destination → Route', rows['Route']['conversion'])
        self.assertIn('HH:MM → decimal hours', rows['Duration']['conversion'])
        table = read_source(source_csv(['Date', 'Aircraft', 'Duration'], [['2026-11-20', 'C172', '90']]))
        form = ColumnMappingForm(dict(choices(table), time_units='minutes'), table=table)
        duration = next(row for row in form.rows() if row['label'] == 'Duration')
        self.assertIn('Minutes → decimal hours', duration['conversion'])

    def test_mapping_advances_through_dates_to_the_exact_imported_values(self):
        batch, table = self.pending_batch()
        response = self.client.post(reverse('csv_mapping', args=[batch.pk]), choices(table))
        self.assertTrue(response.context['preview_ready'])
        self.assertContains(response, 'Jun 25, 2026')
        self.assertContains(response, '1.5')
        self.assertEqual(response.context['file'][0][5], '1.5')
        batch.refresh_from_db()
        self.assertTrue(batch.mapping_complete)
        self.assertEqual(batch.date_order, 'dmy')
        self.assertEqual(batch.column_mapping['duration'], {'column': 5})
        with patch('csv_app.csv_import.email_confirmation'), self.captureOnCommitCallbacks(execute=True):
            confirm_csv_import(SimpleNamespace(user=self.user), batch.pk)
        flight = Flight.objects.get(user=self.user)
        self.assertEqual((flight.date, flight.duration, flight.route), (date(2026, 6, 25), Decimal('1.5'), 'KIAH-KCLL'))

    def test_ambiguous_dates_still_require_a_date_choice_after_mapping(self):
        batch, table = self.pending_batch(source_csv(records=[['05/06/2026', 'C172', 'N12345', 'KIAH', 'KCLL', '01:30', 'true', '1']]))
        response = self.client.post(reverse('csv_mapping', args=[batch.pk]), choices(table))
        self.assertTrue(response.context['date_choice'])
        batch.refresh_from_db()
        self.assertTrue(batch.mapping_complete)
        self.assertEqual(batch.date_order, 'pending')
        self.assertEqual(self.client.post(reverse('csv_upload'), {'batch_id': batch.pk}).status_code, 400)
        response = self.client.post(reverse('csv_date_order', args=[batch.pk]), {'date_order': 'dmy'})
        self.assertContains(response, 'Jun 5, 2026')

    @patch('csv_app.submission.import_csv_batch.apply_async')
    def test_unfinished_mapping_cannot_be_queued_or_imported(self, publish):
        batch, _ = self.pending_batch()
        self.assertEqual(self.client.post(reverse('csv_upload'), {'batch_id': batch.pk}).status_code, 400)
        publish.assert_not_called()
        with self.assertRaises(CSVValidationError):
            confirm_csv_import(SimpleNamespace(user=self.user), batch.pk)
        response = self.client.get(reverse('csv_date_order', args=[batch.pk]))
        self.assertRedirects(response, reverse('csv_mapping', args=[batch.pk]))

    def test_bad_values_keep_the_original_file_available_for_correction(self):
        original = source_csv(records=[['2026-11-26', 'C172', 'N12345', 'KIAH', 'KCLL', '01:99', 'true', '1']])
        batch, table = self.pending_batch(original)
        response = self.client.post(reverse('csv_mapping', args=[batch.pk]), choices(table))
        self.assertTrue(response.context['row_choice'])
        self.assertContains(response, 'Use decimal hours or HH:MM')
        batch.refresh_from_db()
        self.assertTrue(batch.mapping_complete)
        self.assertFalse(batch.rows_complete)
        self.assertIn('01:99', batch.content)
        self.assertFalse(Flight.objects.exists())

    def test_repeated_mapping_does_not_reinterpret_a_reviewed_batch(self):
        batch, table = self.pending_batch()
        url = reverse('csv_mapping', args=[batch.pk])
        self.client.post(url, choices(table))
        batch.refresh_from_db()
        canonical = batch.content
        self.assertEqual(self.client.post(url, choices(table, duration={'value': '99'})).status_code, 302)
        batch.refresh_from_db()
        self.assertEqual(batch.content, canonical)

    def test_live_validation_requires_unused_acknowledgment_without_saving(self):
        batch, table = self.pending_batch(source_csv(['Date', 'Aircraft', 'Duration', 'LEGS'],
            [['2026-11-26', 'C172', '1.5', '1']]))
        original = batch.content
        data = dict(choices(table), validate_only='1')
        url = reverse('csv_mapping', args=[batch.pk])
        invalid = self.client.post(url, data)
        self.assertEqual(invalid.status_code, 200)
        self.assertFalse(invalid.json()['valid'])
        self.assertIn('ignore_unused', invalid.json()['errors'])
        data['ignore_unused'] = 'on'
        self.assertTrue(self.client.post(url, data).json()['valid'])
        batch.refresh_from_db()
        self.assertFalse(batch.mapping_complete)
        self.assertEqual(batch.content, original)
        self.assertFalse(Flight.objects.exists())
        data['map_1'] = ''
        self.assertFalse(self.client.post(url, data).json()['valid'])
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        self.assertEqual(protected.post(url, data).status_code, 403)

    def test_mapping_is_owner_scoped_csrf_protected_and_expires(self):
        batch, table = self.pending_batch()
        url = reverse('csv_mapping', args=[batch.pk])
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        self.assertEqual(protected.post(url, choices(table)).status_code, 403)
        other = get_user_model().objects.create_user('other-mapping')
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, choices(table)).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        seed_records(self.user)
        self.client.force_login(self.user)
        CSVImportBatch.objects.filter(pk=batch.pk).update(created_at=timezone.now() - timedelta(minutes=11))
        self.assertEqual(self.client.get(url).status_code, 410)
        self.assertEqual(self.client.post(url, choices(table)).status_code, 410)

class TimeDetectionTests(SimpleTestCase):
    def form_for(self, durations, units=None):
        table = read_source(source_csv(['Date', 'Aircraft', 'Duration'],
            [['2026-11-26', 'C172', value] for value in durations]))
        data = choices(table)
        if units is not None:
            data['time_units'] = units
        return ColumnMappingForm(data, table=table)

    def test_hhmm_and_fractional_hours_hide_picker(self):
        for durations in (['01:30', '00:25'], ['1.5', '2'], ['0', '0.2'], ['2.0']):
            form = self.form_for(durations)
            self.assertFalse(form.show_time_units)
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data['time_units'], 'hours')

    def test_whole_numbers_need_confirmation(self):
        for durations in (['25'], ['1', '2'], ['30']):
            form = self.form_for(durations)
            self.assertTrue(form.show_time_units)
            self.assertFalse(form.is_valid())
            self.assertIn('time_units', form.errors)

    def test_large_duration_suggests_minutes_but_never_silently_converts(self):
        form = self.form_for(['90', '25'])
        self.assertEqual(form.fields['time_units'].initial, 'minutes')
        self.assertFalse(form.is_valid())
        confirmed = self.form_for(['90', '25'], 'minutes')
        self.assertTrue(confirmed.is_valid(), confirmed.errors)
        converted = normalize_mapping(confirmed.table, confirmed.cleaned_data['mapping'], confirmed.cleaned_data['time_units'])
        self.assertIn('1.5', converted)
        note = next(row['conversion'] for row in confirmed.rows() if row['label'] == 'Duration')
        self.assertIn('90 → 1.5 h', note)
        self.assertIn('25 → 0.4 h', note)

    def test_large_fractional_or_conflicting_values_need_confirmation(self):
        form = self.form_for(['90', '1.5'])
        self.assertTrue(form.show_time_units)
        self.assertFalse(form.is_valid())
        # Long grouped/device entries may legitimately be hours.
        confirmed = self.form_for(['90'], 'hours')
        self.assertTrue(confirmed.is_valid(), confirmed.errors)
        self.assertEqual(confirmed.cleaned_data['time_units'], 'hours')

    def test_hhmm_examples_are_visible(self):
        form = self.form_for(['01:30'])
        note = next(row['conversion'] for row in form.rows() if row['label'] == 'Duration')
        self.assertIn('01:30 → 1.5 h', note)


class UnmatchedExplanationTests(SimpleTestCase):
    def test_missing_heading_explains_why(self):
        table = read_source(source_csv(['Date', 'Aircraft', 'Duration'], [['2026-11-26', 'C172', '1.5']]))
        rows = ColumnMappingForm(table=table).rows()
        night = next(row for row in rows if row['label'] == 'Night')
        self.assertEqual(night['status'], 'No matching column heading found.')

    def test_ambiguous_columns_are_named_and_numbered(self):
        table = read_source(source_csv(['Date', 'Aircraft', 'Duration', 'PIC', 'Pilot in Command'],
            [['2026-11-26', 'C172', '1.5', '1.5', '0.5']]))
        pic = next(row for row in ColumnMappingForm(table=table).rows() if row['label'] == 'PIC')
        self.assertIn('PIC (column 4)', pic['status'])
        self.assertIn('Pilot in Command (column 5)', pic['status'])

    def test_missing_route_or_block_component_is_explained(self):
        table = read_source(source_csv(['Date', 'Aircraft', 'From', 'Block Out'],
            [['2026-11-26', 'C172', 'KIAH', '14:00']]))
        rows = {row['label']: row for row in ColumnMappingForm(table=table).rows()}
        self.assertIn('Both Departure and Destination', rows['Route']['status'])
        self.assertIn('Both Block Out and Block In', rows['Duration']['status'])

class RequiredFlightMappingTests(SimpleTestCase):
    def test_actual_flight_requires_tail_route_and_role_mapping(self):
        table = read_source(source_csv(['Date', 'Aircraft', 'Duration'], [['2026-11-26', 'C172', '1.5']]))
        data = {f'map_{index}': str(table.suggestions()[name]) if name in table.suggestions() else ''
                for index, name in enumerate(MAPPING_FIELDS)}
        form = ColumnMappingForm(data, table=table)
        self.assertFalse(form.is_valid())
        self.assertIn('map_2', form.errors)
        self.assertIn('map_3', form.errors)
        self.assertIn('PIC, SIC, Solo, or Dual', str(form.non_field_errors()))
        self.assertTrue(form.fields['map_4'].required)
        # Explicitly supplying missing values is supported, rather than guessing them.
        data.update(map_2='constant', value_2='N12345', map_3='constant', value_3='KIAH-KCLL',
                    map_5='constant', value_5='yes')
        complete = ColumnMappingForm(data, table=table)
        self.assertTrue(complete.is_valid(), complete.errors)

class RouteConversionDisplayTests(SimpleTestCase):
    def test_airport_inputs_stay_visible_and_combined_route_is_shown(self):
        table = read_source(source_csv())
        form = ColumnMappingForm(table=table)
        route = next(row for row in form.rows() if row['target'] == 'route')
        self.assertEqual(route['combined_label'], 'Combined from column 4 + column 5')
        self.assertEqual(route['combined_preview'], 'KIAH-KCLL')
        sources = {row['index']: row for row in form.source_columns()}
        for index in (3, 4):
            self.assertTrue(sources[index]['used'])
            self.assertFalse(sources[index]['moved'])
            self.assertEqual(sources[index]['usage'], 'Route')
        self.assertNotIn(3, [row['index'] for row in form.unused_columns()])

    def test_inputs_are_not_used_when_route_is_unassigned_or_incomplete(self):
        table = read_source(source_csv())
        data = choices(table)
        data['map_3'] = ''
        form = ColumnMappingForm(data, table=table)
        sources = {row['index']: row for row in form.source_columns()}
        self.assertFalse(sources[3]['used'])
        self.assertFalse(sources[4]['used'])
        data['map_3'] = 'airports'
        data[f'map_{MAPPING_FIELDS.index("destination")}'] = ''
        incomplete = ColumnMappingForm(data, table=table)
        self.assertFalse(incomplete.is_valid())
        self.assertIn('map_3', incomplete.errors)
