from csv_app.tests.record_fixtures import seed_records
import csv
import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from csv_app.formats import prepare_csv
from csv_app.models import CSVImportBatch
from csv_app.validation import HEADERS, OPTIONAL_HEADERS, CSVValidationError, parse_csv
from csv_app.tests.test_atomic_import import content, row
from flights.models import Flight
from csv_app.tests.airport_fixtures import seed_airports


class FormatRecognitionTests(SimpleTestCase):
    def test_reordered_aliases_and_optional_fields_keep_values(self):
        headers = HEADERS + OPTIONAL_HEADERS
        values = row(**{'1': 'EMB145'}) + ['', '', '', '0', '', 'No', '', '']
        order = list(reversed(range(len(headers))))
        headings = [headers[i] for i in order]
        headings[headings.index('pilot in command')] = 'PIC'
        headings[headings.index('aircraft')] = 'Aircraft_Type'
        source, normalized = prepare_csv('\ufeff' + content([[values[i] for i in order]], headings))
        self.assertEqual(source.key, 'direct2logbook-v1')
        self.assertEqual(parse_csv(normalized)[0], parse_csv(content([values], headers))[0])

    def test_legacy_export_with_reordered_columns_gets_zero_approaches(self):
        headers = HEADERS[:10] + HEADERS[11:]
        values = row()
        del values[10]
        _, normalized = prepare_csv(content([values[::-1]], headers[::-1]))
        parsed, _ = parse_csv(normalized)
        self.assertEqual(parsed[0]['approaches'], 0)
        self.assertEqual(parsed[0]['landings_day'], 1)

    def test_unknown_or_ambiguous_headings_are_not_guessed(self):
        duplicate = HEADERS.copy()
        duplicate[6] = 'PIC'
        for headers in [duplicate, HEADERS[:-1], HEADERS + ['unknown column']]:
            with self.subTest(headers=headers), self.assertRaises(CSVValidationError):
                prepare_csv(content(headers=headers))

    def test_source_row_numbers_survive_blank_rows(self):
        _, normalized = prepare_csv(content([[], row(**{'4': 'invalid'})]))
        with self.assertRaisesRegex(CSVValidationError, 'Row 3:'):
            parse_csv(normalized)


@override_settings(SECURE_SSL_REDIRECT=False)
class ImportWizardTests(TestCase):
    def setUp(self):
        seed_airports()
        self.user = get_user_model().objects.create_user('csv-wizard')
        seed_records(self.user)
        self.client.force_login(self.user)

    def test_upload_page_has_steps_template_and_collapsed_guide(self):
        response = self.client.get(reverse('csv_inspect'))
        self.assertContains(response, 'aria-label="Import progress"')
        self.assertContains(response, reverse('csv_template'))
        self.assertContains(response, 'Column guide')
        self.assertContains(response, 'Up to 20 MB · Up to 10,000 flights')
        self.assertContains(response, 'data-max-bytes="20971520"')
        self.assertContains(response, 'data-file-drop')
        self.assertContains(response, 'data-review-spinner')
        self.assertContains(response, 'Reading your file and matching columns…')
        self.assertContains(response, 'Drop a CSV or TSV here, or choose a file.')
        self.assertContains(response, '/static/csv_app/js/import.js')
        self.assertContains(response, 'data-import-url="' + reverse('csv_upload') + '"')
        self.assertNotContains(response, 'LogTen')
        self.assertNotContains(response, 'Logbook Pro')

    def test_template_is_downloadable_and_valid_for_the_current_parser(self):
        response = self.client.get(reverse('csv_template'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        records = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(records[0], HEADERS + OPTIONAL_HEADERS)
        self.assertEqual(len(records[0]), len(records[1]))
        self.assertEqual(len(parse_csv(response.content.decode())[0]), 1)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('csv_template')).status_code, 302)

    def test_review_normalizes_columns_without_creating_flights(self):
        upload = SimpleUploadedFile('export.csv', content([row()[::-1]], HEADERS[::-1]).encode())
        response = self.client.post(reverse('csv_inspect'), {'file': upload})
        self.assertTrue(response.context['preview_ready'])
        self.assertContains(response, 'Check these conversions')
        self.assertContains(response, 'No flights added yet.')
        batch = CSVImportBatch.objects.get(user=self.user)
        self.assertEqual(list(csv.reader(io.StringIO(batch.content)))[0], HEADERS)
        self.assertFalse(Flight.objects.filter(user=self.user).exists())

    def test_unknown_headings_open_mapping_without_saving_flights(self):
        upload = SimpleUploadedFile('unknown.csv', b'When,Plane,Time\n2026-11-26,C172,1.5\n')
        response = self.client.post(reverse('csv_inspect'), {'file': upload})
        self.assertContains(response, 'Match your columns')
        self.assertFalse(response.context['batch'].mapping_complete)
        self.assertFalse(Flight.objects.filter(user=self.user).exists())
