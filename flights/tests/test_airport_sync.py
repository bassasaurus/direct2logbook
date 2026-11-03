import csv
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from flights.airport_resolution import resolve_route
from flights.airport_sync import parse_sources, sync_airports
from flights.management.commands.sync_airports import TrustedRedirects
from flights.models import AirportCode, MapData


HEADERS = ['id', 'ident', 'type', 'name', 'latitude_deg', 'longitude_deg', 'elevation_ft',
           'iso_country', 'iso_region', 'municipality', 'icao_code', 'iata_code', 'gps_code', 'local_code']


def csv_bytes(rows, fields):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode('utf-8')


def airport_row(**kwargs):
    row = dict(zip(HEADERS, ['100', 'KLBX', 'medium_airport', 'Texas Gulf Coast Regional Airport',
                           '29.1', '-95.46', '25', 'US', 'US-TX', 'Angleton', 'KLBX', 'LJN', 'KLBX', 'LBX']))
    row.update(kwargs)
    return row


COUNTRIES = csv_bytes([{'code': 'US', 'name': 'United States'}, {'code': 'PH', 'name': 'Philippines'}], ['code', 'name'])
REGIONS = csv_bytes([{'code': 'US-TX', 'name': 'Texas'}, {'code': 'PH-MDC', 'name': 'Occidental Mindoro'}], ['code', 'name'])


def parsed(*rows):
    return parse_sources(csv_bytes(rows, HEADERS), COUNTRIES, REGIONS)


class AirportSyncTests(TestCase):
    def legacy(self, **kwargs):
        values = dict(icao='KLBX', iata='LBX', name='Texas Gulf Coast', city='Angleton',
                      country='United States', latitude=29.1, longitude=-95.46)
        values.update(kwargs)
        return MapData.objects.create(**values)

    def test_preview_leaves_all_airport_data_untouched(self):
        airport = self.legacy()
        report = sync_airports(*parsed(airport_row()))
        self.assertEqual(report['updated'], 1)
        airport.refresh_from_db()
        self.assertIsNone(airport.ourairports_id)
        self.assertEqual(airport.name, 'Texas Gulf Coast')
        self.assertEqual(MapData.objects.count(), 1)
        self.assertFalse(AirportCode.objects.exists())

    def test_apply_preserves_pk_and_both_faa_and_iata_codes_and_is_idempotent(self):
        airport = self.legacy()
        report = sync_airports(*parsed(airport_row()), apply=True)
        airport.refresh_from_db()
        self.assertEqual(airport.ourairports_id, 100)
        self.assertEqual(airport.iata, 'LJN')
        self.assertEqual(airport.state, 'Texas')
        self.assertEqual(report['updated'], 1)
        self.assertEqual(MapData.objects.count(), 1)
        self.assertTrue(airport.codes.filter(code='LBX', kind='faa').exists())
        for code in ('LBX', 'LJN', 'KLBX'):
            self.assertEqual(resolve_route(code)[0]['airport'].pk, airport.pk)
        again = sync_airports(*parsed(airport_row()), apply=True)
        self.assertEqual((again['updated'], again['aliases_added'], again['unchanged']), (0, 0, 1))

    def test_new_airport_added_and_closed_or_absent_airports_never_deleted(self):
        closed = self.legacy(ourairports_id=100)
        absent = self.legacy(icao='KOLD', iata='OLD', ourairports_id=200)
        report = sync_airports(*parsed(airport_row(type='closed', icao_code='', iata_code='', gps_code='', local_code=''),
                                      airport_row(id='300', ident='12TX', type='small_airport', name='New Airport',
                                                  icao_code='', iata_code='', gps_code='12TX', local_code='12TX', latitude_deg='30')), apply=True)
        closed.refresh_from_db()
        self.assertEqual(closed.airport_type, 'closed')
        self.assertEqual((closed.icao, closed.iata), ('KLBX', 'LBX'))
        self.assertTrue(MapData.objects.filter(pk=absent.pk).exists())
        self.assertEqual((report['created'], report['retained_missing']), (1, 1))
        self.assertEqual(resolve_route('12TX')[0]['airport'].name, 'New Airport')

    def test_code_change_keeps_old_codes_and_saved_airport_choice_pk(self):
        airport = self.legacy(ourairports_id=100)
        sync_airports(*parsed(airport_row(icao_code='KNEW', iata_code='NEW', gps_code='KNEW', local_code='NEW')), apply=True)
        airport.refresh_from_db()
        self.assertEqual(airport.icao, 'KNEW')
        for code in ('KLBX', 'LBX', 'NEW', 'KNEW'):
            self.assertEqual(resolve_route(code)[0]['airport'].pk, airport.pk)
        choice = {'route': 'LBX', 'airports': {'0': airport.pk}}
        self.assertEqual(resolve_route('LBX', choice)[0]['airport'].pk, airport.pk)

    def test_duplicate_legacy_icaos_and_large_coordinate_changes_are_skipped(self):
        self.legacy()
        self.legacy(name='Duplicate')
        report = sync_airports(*parsed(airport_row()), apply=True)
        self.assertEqual((report['created'], report['updated']), (0, 0))
        self.assertIn('multiple legacy', report['skipped'][0]['reason'])
        MapData.objects.all().delete()
        airport = self.legacy(ourairports_id=100)
        report = sync_airports(*parsed(airport_row(latitude_deg='50')), apply=True)
        airport.refresh_from_db()
        self.assertEqual(airport.latitude, 29.1)
        self.assertIn('10 km', report['skipped'][0]['reason'])

    def test_invalid_rows_are_reported_and_duplicate_source_ids_reject_whole_input(self):
        records, skipped = parsed(airport_row(), airport_row(id='101', latitude_deg='nan'))
        self.assertEqual(len(records), 1)
        self.assertEqual(skipped[0]['reason'], 'invalid coordinates')
        with self.assertRaisesMessage(ValueError, 'Duplicate OurAirports IDs'):
            parsed(airport_row(), airport_row())
        with self.assertRaises(ValueError):
            parse_sources(b'id,name\n100,Airport\n', COUNTRIES, REGIONS)

    def test_failed_apply_rolls_back_airport_updates(self):
        airport = self.legacy()
        with patch.object(AirportCode.objects, 'bulk_create', side_effect=RuntimeError('write failed')):
            with self.assertRaises(RuntimeError):
                sync_airports(*parsed(airport_row()), apply=True)
        airport.refresh_from_db()
        self.assertIsNone(airport.ourairports_id)
        self.assertEqual(airport.iata, 'LBX')

    def test_command_defaults_to_preview_and_records_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for name, data in [('airports', csv_bytes([airport_row()], HEADERS)), ('countries', COUNTRIES), ('regions', REGIONS)]:
                (base / (name + '.csv')).write_bytes(data)
            args = dict(airports_file=base/'airports.csv', countries_file=base/'countries.csv', regions_file=base/'regions.csv',
                        report=base/'report.json', stdout=io.StringIO())
            call_command('sync_airports', **args)
            self.assertFalse(MapData.objects.exists())
            report = json.loads(args['report'].read_text())
            self.assertFalse(report['applied'])
            self.assertEqual(len(report['source_sha256']['airports']), 64)
            call_command('sync_airports', apply=True, **args)
            self.assertEqual(MapData.objects.count(), 1)
        with self.assertRaises(CommandError):
            call_command('sync_airports', airports_file=Path('missing.csv'))

    def test_download_failure_and_untrusted_redirect_do_not_change_airports(self):
        airport = self.legacy()
        with patch('flights.management.commands.sync_airports.download', side_effect=OSError('network failed')):
            with self.assertRaisesMessage(CommandError, 'network failed'):
                call_command('sync_airports', apply=True)
        airport.refresh_from_db()
        self.assertIsNone(airport.ourairports_id)
        self.assertEqual(MapData.objects.count(), 1)
        with self.assertRaisesMessage(ValueError, 'untrusted destination'):
            TrustedRedirects().redirect_request(None, None, 302, '', {}, 'https://example.com/airports.csv')

    def test_duplicate_canonical_source_ids_and_invalid_iata_are_rejected(self):
        with self.assertRaisesMessage(ValueError, 'Duplicate OurAirports IDs'):
            parsed(airport_row(id='100'), airport_row(id='0100'))
        records, skipped = parsed(airport_row(), airport_row(id='101', iata_code='INVALID'))
        self.assertEqual(len(records), 1)
        self.assertEqual(skipped[0]['reason'], 'invalid IATA code')

    def test_reassigned_legacy_icao_stays_skipped_on_repeat_sync(self):
        airport = self.legacy(icao='KOLD')
        rows = parsed(airport_row(icao_code='KNEW', gps_code='KNEW'),
                      airport_row(id='200', name='Other airport', icao_code='KOLD',
                                  gps_code='KOLD', iata_code='OTH', local_code='OTH', latitude_deg='40'))
        first = sync_airports(*rows, apply=True)
        second = sync_airports(*rows, apply=True)
        self.assertEqual((first['created'], second['created'], second['updated']), (0, 0, 0))
        self.assertEqual(MapData.objects.count(), 1)
        airport.refresh_from_db()
        self.assertEqual(airport.icao, 'KNEW')
        self.assertTrue(airport.codes.filter(code='KOLD', kind='icao').exists())
        self.assertEqual(second['skipped'][0]['source_id'], 200)
