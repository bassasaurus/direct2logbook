from csv_app.tests.record_fixtures import seed_records
import csv
import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from csv_app.airports import normalize_airport_routes
from csv_app.forms import ColumnMappingForm
from csv_app.mapping import read_source
from csv_app.models import CSVImportBatch
from csv_app.tests.airport_fixtures import seed_airports
from csv_app.tests.test_atomic_import import content, row, device_row
from csv_app.tests.test_mapping import choices, source_csv
from csv_app.validation import CSVValidationError, parse_csv
from flights.models import AirportCode, Flight, MapData


class AirportColumnMatchingTests(SimpleTestCase):
    def test_explicit_airport_columns_prefer_icao_then_iata_then_faa(self):
        table = read_source(source_csv(['Departure IATA', 'Departure ICAO', 'Departure FAA', 'Destination FAA', 'Destination IATA'],
                                       [['IAH', 'KIAH', 'IAH', 'CLL', 'CLL']]))
        self.assertEqual(table.suggestions()['departure'], 1)
        self.assertEqual(table.suggestions()['destination'], 4)
        form = ColumnMappingForm(table=table)
        self.assertEqual(form['map_3'].value(), 'airports')

    def test_departure_and_arrival_times_are_not_matched_as_airports(self):
        table = read_source(source_csv(['Departure', 'Arrival'], [['10:30', '12:00']]))
        self.assertNotIn('departure', table.suggestions())
        self.assertNotIn('destination', table.suggestions())
        table = read_source(source_csv(['Departure', 'Arrival'], [['IAH', 'CLL']]))
        self.assertEqual(table.suggestions(), {'departure': 0, 'destination': 1})


@override_settings(SECURE_SSL_REDIRECT=False)
class CSVAirportValidationTests(TestCase):
    def setUp(self):
        seed_airports()
        self.user = get_user_model().objects.create_user('csv-airports')
        seed_records(self.user)
        self.client.force_login(self.user)
        self.no_icao = MapData.objects.create(name='IATA example', iata='XAA', country='United States')
        AirportCode.objects.create(airport=self.no_icao, code='XAA', kind='iata')
        AirportCode.objects.create(airport=self.no_icao, code='9AA', kind='faa')
        self.faa_only = MapData.objects.create(name='FAA example', country='United States')
        AirportCode.objects.create(airport=self.faa_only, code='1G3', kind='faa')

    def normalized(self, route):
        raw = content([row(**{'3': route})])
        return parse_csv(normalize_airport_routes(raw, parse_csv(raw)[0]))[0][0]['route']

    def test_route_uses_each_airports_best_available_code_without_invented_prefixes(self):
        self.assertEqual(self.normalized('IAH-9AA-1G3'), 'KIAH-XAA-1G3')
        self.assertEqual(self.normalized('KIAH-CLL'), 'KIAH-KCLL')
        self.assertEqual(self.normalized('IAH-IAH'), 'KIAH-KIAH')

    def test_historical_aliases_resolve_through_the_shared_airport_database(self):
        airport = MapData.objects.get(icao='KIAH')
        AirportCode.objects.create(airport=airport, code='OLD', kind='legacy')
        self.assertEqual(self.normalized('OLD-CLL'), 'KIAH-KCLL')

    def test_unknown_and_ambiguous_airports_are_rejected_with_row_numbers(self):
        with self.assertRaisesRegex(CSVValidationError, 'Row 2: Airport not found: ZZZZ'):
            self.normalized('KIAH-ZZZZ')
        MapData.objects.create(icao='KTKI', iata='TKI', name='McKinney', country='United States')
        MapData.objects.create(iata='TKI', name='Tokeen', country='United States')
        with self.assertRaisesRegex(CSVValidationError, 'Row 2: Multiple airports match TKI'):
            self.normalized('TKI-KIAH')

    def test_ambiguous_iata_is_not_substituted_for_a_unique_faa_identifier(self):
        MapData.objects.create(iata='XAA', name='Other US airport', country='United States')
        self.assertEqual(self.normalized('9AA-KIAH'), '9AA-KIAH')

    def test_simulator_routes_do_not_require_airport_validation(self):
        raw = content([device_row(**{'3': 'Not an airport'})])
        parsed, _ = parse_csv(raw)
        self.assertEqual(parse_csv(normalize_airport_routes(raw, parsed))[0][0]['route'], parsed[0]['route'])

    def test_mapping_from_airport_columns_shows_the_validated_route_in_preview(self):
        original = source_csv(records=[['2026-11-26', 'C172', 'N12345', 'iah', 'cll', '1.5', 'true', '1']])
        response = self.client.post(reverse('csv_inspect'), {'file': SimpleUploadedFile('flight.csv', original.encode())})
        batch = response.context['batch']
        response = self.client.post(reverse('csv_mapping', args=[batch.pk]), choices(read_source(original)))
        self.assertTrue(response.context['preview_ready'])
        self.assertContains(response, 'KIAH-KCLL')
        batch.refresh_from_db()
        self.assertEqual(parse_csv(batch.content)[0][0]['route'], 'KIAH-KCLL')
        self.assertFalse(Flight.objects.exists())

    def test_bad_airport_opens_row_corrections_and_cannot_be_submitted(self):
        original = source_csv(records=[['2026-11-26', 'C172', 'N12345', 'IAH', 'ZZZZ', '1.5', 'true', '1']])
        response = self.client.post(reverse('csv_inspect'), {'file': SimpleUploadedFile('flight.csv', original.encode())})
        batch = response.context['batch']
        response = self.client.post(reverse('csv_mapping', args=[batch.pk]), choices(read_source(original)))
        self.assertTrue(response.context['row_choice'])
        self.assertContains(response, 'Airport not found: ZZZZ')
        batch.refresh_from_db()
        self.assertTrue(batch.mapping_complete)
        self.assertFalse(batch.rows_complete)
        with patch('csv_app.submission.import_csv_batch.apply_async') as publish:
            self.assertEqual(self.client.post(reverse('csv_upload'), {'batch_id': batch.pk}).status_code, 400)
        publish.assert_not_called()

    def test_route_lookups_are_batched_instead_of_one_query_per_flight(self):
        raw = content([row(**{'3': 'IAH-CLL'}) for _ in range(100)])
        parsed, _ = parse_csv(raw)
        with self.assertNumQueries(4):
            result = normalize_airport_routes(raw, parsed)
        self.assertEqual(len(parse_csv(result)[0]), 100)
