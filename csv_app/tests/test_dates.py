from csv_app.tests.record_fixtures import seed_records
import csv
import io
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from csv_app.csv_import import confirm_csv_import
from csv_app.dates import AmbiguousDates, interpret_dates
from csv_app.models import CSVImportBatch
from csv_app.tests.test_atomic_import import content, row
from csv_app.validation import CSVValidationError, parse_csv
from flights.models import Flight
from csv_app.tests.airport_fixtures import seed_airports


def dated_csv(*dates):
    return content([row(**{'0': value}) for value in dates])


class CSVDateDetectionTests(SimpleTestCase):
    def test_detects_numeric_order_using_all_rows_including_later_evidence(self):
        for values, expected_order, expected_dates in [
            (['05/06/2026', '25/06/2026'], 'dmy', ['2026-06-05', '2026-06-25']),
            (['05/06/2026', '06/25/2026'], 'mdy', ['2026-05-06', '2026-06-25']),
            (['05-06-2026', '25-06-2026'], 'dmy', ['2026-06-05', '2026-06-25']),
        ]:
            with self.subTest(values=values):
                normalized, order = interpret_dates(dated_csv(*values))
                self.assertEqual(order, expected_order)
                self.assertEqual([r[0] for r in list(csv.reader(io.StringIO(normalized)))[1:]], expected_dates)

    def test_ambiguous_dates_require_choice_and_offer_interpreted_examples(self):
        with self.assertRaises(AmbiguousDates) as error:
            interpret_dates(dated_csv('05/06/2026', '07/08/2026'))
        self.assertEqual(error.exception.examples[0],
                         {'original': '05/06/2026', 'mdy': 'May 6, 2026', 'dmy': 'Jun 5, 2026'})
        for choice, expected in [('mdy', date(2026, 5, 6)), ('dmy', date(2026, 6, 5))]:
            normalized, actual = interpret_dates(dated_csv('05/06/2026'), choice)
            self.assertEqual(actual, choice)
            self.assertEqual(parse_csv(normalized)[0][0]['date'], expected)

    def test_identical_interpretations_do_not_require_a_choice(self):
        normalized, order = interpret_dates(dated_csv('06/06/2026', '11/11/2026'))
        self.assertEqual(order, 'unambiguous')
        self.assertEqual(parse_csv(normalized)[0][0]['date'], date(2026, 6, 6))

    def test_iso_and_named_dates_are_preserved_alongside_numeric_dates(self):
        normalized, order = interpret_dates(dated_csv('2026-06-05', 'Jun 5, 2026', '25/06/2026'))
        self.assertEqual(order, 'dmy')
        self.assertEqual([r['date'] for r in parse_csv(normalized)[0]],
                         [date(2026, 6, 5), date(2026, 6, 5), date(2026, 6, 25)])

    def test_mixed_orders_are_rejected_instead_of_guessing_per_row(self):
        for choice in ['auto', 'mdy', 'dmy']:
            with self.subTest(choice=choice), self.assertRaises(CSVValidationError):
                interpret_dates(dated_csv('25/06/2026', '06/25/2026'), choice)

    def test_invalid_dates_and_wrong_explicit_order_are_rejected(self):
        for value, choice in [('29/02/2026', 'auto'), ('02/29/2026', 'auto'),
                              ('31/04/2026', 'auto'), ('25/06/2026', 'mdy'),
                              ('06/25/2026', 'dmy'), ('bad-date', 'auto')]:
            with self.subTest(value=value, choice=choice), self.assertRaisesRegex(CSVValidationError, 'Row 2:'):
                interpret_dates(dated_csv(value), choice)
        for value in ['29/02/2024', '02/29/2024']:
            normalized, _ = interpret_dates(dated_csv(value))
            self.assertEqual(parse_csv(normalized)[0][0]['date'], date(2024, 2, 29))


@override_settings(SECURE_SSL_REDIRECT=False)
class CSVDateWizardTests(TestCase):
    def setUp(self):
        seed_airports()
        self.user = get_user_model().objects.create_user('csv-dates')
        seed_records(self.user)
        self.client.force_login(self.user)

    def upload(self, *dates):
        return self.client.post(reverse('csv_inspect'),
            {'file': SimpleUploadedFile('dates.csv', dated_csv(*dates).encode())})

    def pending_batch(self):
        response = self.upload('05/06/2026')
        self.assertTrue(response.context['date_choice'])
        return response.context['batch']

    def test_unambiguous_upload_goes_straight_to_interpreted_preview(self):
        response = self.upload('25/06/2026', '05/06/2026')
        self.assertTrue(response.context['preview_ready'])
        self.assertContains(response, 'Jun 25, 2026')
        self.assertContains(response, 'Jun 5, 2026')
        batch = response.context['batch']
        self.assertEqual(batch.date_order, 'dmy')
        self.assertIn('2026-06-05', batch.content)
        self.assertFalse(Flight.objects.exists())

    @patch('csv_app.submission.import_csv_batch.apply_async')
    def test_pending_choice_cannot_be_submitted_or_imported_directly(self, publish):
        batch = self.pending_batch()
        self.assertEqual(batch.date_order, 'pending')
        response = self.client.post(reverse('csv_upload'), {'batch_id': batch.pk})
        self.assertEqual(response.status_code, 400)
        self.assertIn('Choose a date format', response.json()['message'])
        publish.assert_not_called()
        with self.assertRaises(CSVValidationError):
            confirm_csv_import(SimpleNamespace(user=self.user), batch.pk)
        self.assertFalse(Flight.objects.exists())

    def test_choice_is_saved_as_iso_and_matches_the_imported_flight(self):
        batch = self.pending_batch()
        response = self.client.post(reverse('csv_date_order', args=[batch.pk]), {'date_order': 'dmy'})
        self.assertTrue(response.context['preview_ready'])
        self.assertContains(response, 'Jun 5, 2026')
        self.assertNotContains(response, 'May 6, 2026')
        batch.refresh_from_db()
        self.assertEqual(batch.date_order, 'dmy')
        self.assertEqual(parse_csv(batch.content)[0][0]['date'], date(2026, 6, 5))
        with patch('csv_app.csv_import.email_confirmation'), self.captureOnCommitCallbacks(execute=True):
            confirm_csv_import(SimpleNamespace(user=self.user), batch.pk)
        self.assertEqual(Flight.objects.get(user=self.user).date, date(2026, 6, 5))

    def test_repeated_choice_does_not_reinterpret_a_reviewed_batch(self):
        batch = self.pending_batch()
        url = reverse('csv_date_order', args=[batch.pk])
        self.client.post(url, {'date_order': 'dmy'})
        response = self.client.post(url, {'date_order': 'mdy'})
        batch.refresh_from_db()
        self.assertEqual(batch.date_order, 'dmy')
        self.assertContains(response, 'Jun 5, 2026')

    def test_no_choice_is_preselected_and_missing_or_invalid_choices_stay_pending(self):
        batch = self.pending_batch()
        url = reverse('csv_date_order', args=[batch.pk])
        self.assertNotContains(self.client.get(url), 'checked')
        for choice in ['', 'guess']:
            response = self.client.post(url, {'date_order': choice})
            self.assertTrue(response.context['date_choice'])
            self.assertTrue(response.context['date_form'].errors)
            batch.refresh_from_db()
            self.assertEqual(batch.date_order, 'pending')

    def test_date_choice_is_owner_scoped_and_csrf_protected(self):
        batch = self.pending_batch()
        url = reverse('csv_date_order', args=[batch.pk])
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        self.assertEqual(protected.post(url, {'date_order': 'dmy'}).status_code, 403)
        other = get_user_model().objects.create_user('other-csv-dates')
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {'date_order': 'dmy'}).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_pending_date_choices_expire_like_other_previews(self):
        batch = self.pending_batch()
        CSVImportBatch.objects.filter(pk=batch.pk).update(created_at=timezone.now() - timedelta(minutes=11))
        url = reverse('csv_date_order', args=[batch.pk])
        self.assertEqual(self.client.get(url).status_code, 410)
        self.assertEqual(self.client.post(url, {'date_order': 'dmy'}).status_code, 410)
        self.assertFalse(Flight.objects.exists())

    def test_mixed_file_opens_corrections_and_cannot_be_imported(self):
        response = self.upload('25/06/2026', '06/25/2026')
        self.assertContains(response, 'Use one date order throughout the file.')
        self.assertTrue(response.context['row_choice'])
        self.assertFalse(response.context['batch'].rows_complete)
