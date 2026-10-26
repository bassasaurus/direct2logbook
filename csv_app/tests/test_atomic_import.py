import csv
import io
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse

from csv_app.csv_import import csv_import
from csv_app.validation import HEADERS, parse_csv, CSVValidationError, MAX_BYTES
from flights.models import Flight, Aircraft, TailNumber, Approach, Total, Stat


def row(**changes):
    values = ['2026-10-20', 'C172', 'N12345', 'IAH MCO', '1.5', '1.5', '0', '1.5',
              '0.2', '0.3', '2', '1', '0', '0', '0', '0', '0', '0', 'Training']
    for index, value in changes.items():
        values[int(index)] = value
    return values


def content(rows=None, headers=None):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers or HEADERS)
    writer.writerows(rows if rows is not None else [row()])
    return output.getvalue()


class CSVValidationTests(SimpleTestCase):
    def test_typed_values_and_normalized_preview(self):
        rows, preview = parse_csv(content())
        self.assertEqual(rows[0]['approaches'], 2)
        self.assertEqual(rows[0]['duration'], Decimal('1.5'))
        self.assertEqual(rows[0]['route'], 'IAH-MCO')
        self.assertEqual(preview[0][3], 'IAH-MCO')

    def test_old_eighteen_column_download_is_accepted(self):
        legacy = row()
        del legacy[10]
        rows, _ = parse_csv(content([legacy], HEADERS[:10] + HEADERS[11:]))
        self.assertEqual(rows[0]['approaches'], 0)
        self.assertEqual(rows[0]['landings_day'], 1)
        self.assertEqual(rows[0]['remarks'], 'Training')

    def test_invalid_data_has_row_number(self):
        for index, value in [(0, 'bad-date'), (1, ''), (1, 'ABCDE'), (2, 'long' * 5), (4, 'NaN'),
                             (4, '-1'), (4, '100'), (10, '1.5'), (11, 'bad'), (18, 'x' * 501)]:
            with self.subTest(index=index, value=value):
                with self.assertRaisesRegex(CSVValidationError, 'Row 2:'):
                    parse_csv(content([row(**{str(index): value})]))

    def test_empty_malformed_and_short_files_are_rejected(self):
        for value in ['', content([]), content([['short']]), 'wrong,headers\n1,2',
                      content().replace('Training', '\x00'), ','.join(HEADERS) + '\n"unclosed']:
            with self.subTest(value=value[:30]):
                with self.assertRaises(CSVValidationError):
                    parse_csv(value)

    def test_limits_are_enforced(self):
        with self.assertRaises(CSVValidationError):
            parse_csv(content([row()] * 1001))
        with self.assertRaises(CSVValidationError):
            parse_csv('x' * (MAX_BYTES + 1))


@override_settings(SECURE_SSL_REDIRECT=False)
class CSVAtomicImportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='csv_atomic', email='atomic@example.com')
        self.request = SimpleNamespace(user=self.user)
        self.client.force_login(self.user)

    def import_file(self, text=None):
        return csv_import.run(self.request, text or content())

    def test_success_imports_typed_approaches_and_updates_totals(self):
        self.assertEqual(self.import_file(), 1)
        self.assertEqual(Flight.objects.get().duration, Decimal('1.5'))
        self.assertEqual(Approach.objects.get().number, 2)
        self.assertEqual(Total.objects.get(user=self.user, total='All').total_time, Decimal('1.5'))
        self.assertEqual(Stat.objects.get(user=self.user).total_time, Decimal('1.5'))

    def test_invalid_later_row_leaves_no_partial_import(self):
        with self.assertRaises(CSVValidationError):
            self.import_file(content([row(), row(**{'4': 'invalid'})]))
        self.assertFalse(Flight.objects.exists())
        self.assertFalse(Aircraft.objects.exists())
        self.assertFalse(TailNumber.objects.exists())
        self.assertFalse(Approach.objects.exists())

    def test_later_write_failure_rolls_back_normal_signal_updates(self):
        original = Approach.objects.create
        calls = 0
        def create(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError('second approach failed')
            return original(**kwargs)
        with self.captureOnCommitCallbacks(execute=True) as notifications:
            with patch('csv_app.csv_import.Approach.objects.create', side_effect=create):
                with self.assertRaises(RuntimeError):
                    self.import_file(content([row(), row(**{'2': 'N54321'})]))
        self.assertEqual(notifications, [])
        self.assertFalse(Flight.objects.exists())
        self.assertFalse(Approach.objects.exists())
        self.assertFalse(Aircraft.objects.exists())
        self.assertFalse(TailNumber.objects.exists())
        self.assertFalse(Stat.objects.exists())
        self.assertEqual(Total.objects.get(user=self.user, total='All').total_time, 0)

    def test_existing_data_survives_failed_import(self):
        self.import_file()
        original_id = Flight.objects.get().pk
        with self.assertRaises(CSVValidationError):
            self.import_file(content([row(**{'4': 'bad'})]))
        self.assertEqual(list(Flight.objects.values_list('pk', flat=True)), [original_id])
        self.assertEqual(Total.objects.get(user=self.user, total='All').total_time, Decimal('1.5'))

    @patch('csv_app.csv_import.email_confirmation')
    def test_email_runs_only_after_commit(self, notify):
        with self.captureOnCommitCallbacks(execute=True):
            self.import_file()
            notify.assert_not_called()
        notify.assert_called_once_with(self.request)

    @patch('csv_app.csv_import.email_confirmation', side_effect=TimeoutError('mail'))
    def test_email_failure_does_not_undo_or_fail_completed_import(self, notify):
        with self.assertLogs('django.csv_app', level='ERROR'):
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(self.import_file(), 1)
        self.assertEqual(Flight.objects.count(), 1)

    def test_conflicting_registration_rolls_back_new_aircraft(self):
        aircraft = Aircraft.objects.create(user=self.user, aircraft_type='PA28')
        TailNumber.objects.create(user=self.user, aircraft=aircraft, registration='N12345')
        with self.assertRaises(CSVValidationError):
            self.import_file()
        self.assertFalse(Flight.objects.exists())
        self.assertFalse(Aircraft.objects.filter(aircraft_type='C172').exists())

    def test_preview_validation_errors_do_not_leave_old_session_file(self):
        session = self.client.session
        session['file'] = content()
        session.save()
        upload = SimpleUploadedFile('bad.csv', b'wrong,headers\n1,2')
        response = self.client.post(reverse('csv_inspect'), {'file': upload})
        self.assertTrue(response.context['inspect_form'].errors)
        self.assertNotIn('file', self.client.session)
        self.assertNotContains(response, 'id="csv_upload"')

    def test_preview_accepts_valid_utf8_without_saving_flights(self):
        upload = SimpleUploadedFile('flights.csv', content().encode())
        response = self.client.post(reverse('csv_inspect'), {'file': upload})
        self.assertTrue(response.context['preview_ready'])
        self.assertNotIn('file', self.client.session)
        self.assertEqual(response.context['batch'].user_id, self.user.pk)
        self.assertFalse(Flight.objects.exists())

    def test_bad_encoding_and_missing_session_are_controlled(self):
        response = self.client.post(reverse('csv_inspect'), {'file': SimpleUploadedFile('bad.csv', b'\xff\xfe')})
        self.assertTrue(response.context['inspect_form'].errors)
        self.assertEqual(self.client.post(reverse('csv_upload')).status_code, 400)

    def test_invalid_batch_content_still_fails_atomically_in_worker_service(self):
        from csv_app.models import CSVImportBatch
        from csv_app.csv_import import confirm_csv_import
        batch = CSVImportBatch.objects.create(user=self.user, content=content([row(**{'4': 'invalid'})]), row_count=1)
        with self.assertRaises(CSVValidationError):
            confirm_csv_import(self.request, batch.pk)
        self.assertFalse(Flight.objects.exists())

    def test_export_import_columns_align(self):
        self.import_file()
        response = self.client.get(reverse('csv_download'))
        rows, _ = parse_csv(response.content.decode())
        self.assertEqual(rows[0]['approaches'], 2)
        self.assertEqual(rows[0]['landings_day'], 1)
        self.assertEqual(rows[0]['remarks'], 'Training')
