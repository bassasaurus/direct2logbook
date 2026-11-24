from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, TransactionTestCase

from flights.classification_audit import classification_baseline
from flights.models import Aircraft, Flight, Imported, Stat, TailNumber, Total


class ClassificationAuditTests(TestCase):
    today = date(2026, 11, 24)

    def setUp(self):
        clock = patch('flights.rolling_stats.timezone.localdate', return_value=self.today)
        clock.start()
        self.addCleanup(clock.stop)
        self.user = get_user_model().objects.create_user(username='classification-audit')
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='C172',
            aircraft_category='A', aircraft_class='SEL', piston=True, small=True)
        self.tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft,
                                             registration='N172', is_91=True)
        self.flight = Flight.objects.create(user=self.user, aircraft_type=self.aircraft, registration=self.tail,
            route='SEA-PDX', date=self.today, duration='1.7', pilot_in_command=True, dual=True,
            night='0.3', landings_day=2, landings_night=1)
        Flight.objects.create(user=self.user, aircraft_type=self.aircraft, simulator=True, device_type='FFS',
            device_id='TEST', date=self.today, duration='2.1', instrument='0.5', dual=True)
        Imported.objects.create(user=self.user, aircraft_type=self.aircraft, total_time='10.2',
            pilot_in_command='7.1', dual='2.3', simulator='0.4', landings_day=3,
            last_flown=date(2020, 1, 1))

    def report(self, **kwargs):
        return classification_baseline(as_of=self.today, **kwargs)

    def test_baseline_matches_sources_with_overlap_nulls_and_separate_simulator_time(self):
        report = self.report()
        self.assertEqual(report['issues'], [])
        self.assertEqual(report['finding_counts'], {})
        totals = report['users'][0]['source_totals']
        self.assertEqual(totals['total_time'], Decimal('11.9'))
        self.assertEqual(totals['pilot_in_command'], Decimal('8.8'))
        self.assertEqual(totals['dual'], Decimal('4.0'))
        self.assertEqual(totals['simulator'], Decimal('2.5'))
        self.assertEqual(totals['instrument'], Decimal('0'))
        self.assertEqual(totals['landings_total'], Decimal('6'))
        self.assertEqual(totals['last_30'], Decimal('1.7'))
        self.assertEqual(report['aircraft'][0]['counts'],
                         {'flights': 1, 'simulator_sessions': 1, 'imported_balances': 1, 'tailnumbers': 1})

    def test_rolling_bounds_and_future_records_are_independently_calculated(self):
        for age in (30, 31, -1):
            Flight.objects.create(user=self.user, aircraft_type=self.aircraft, registration=self.tail,
                route='SEA-PDX', date=self.today - timedelta(days=age), duration='0.3')
        report = self.report()
        self.assertEqual(report['issues'], [])
        totals = report['users'][0]['source_totals']
        self.assertEqual(totals['total_time'], Decimal('12.8'))
        self.assertEqual(totals['last_30'], Decimal('2.0'))
        self.assertEqual(totals['last_60'], Decimal('2.3'))
        self.assertEqual(totals['last_flown'], self.today)

    def test_reports_discrepancies_without_repairing_or_executing_writes(self):
        total = Total.objects.get(user=self.user, total='All')
        Total.objects.filter(pk=total.pk).update(total_time='999.0', last_30='77.0')
        before = {model.__name__: list(model.objects.order_by('pk').values())
                  for model in (Aircraft, Flight, Imported, Total, Stat)}

        def select_only(execute, sql, params, many, context):
            self.assertTrue(sql.lstrip().upper().startswith('SELECT'), sql)
            return execute(sql, params, many, context)

        with connection.execute_wrapper(select_only):
            report = self.report()
        mismatches = [item for item in report['issues'] if item['kind'] == 'summary_mismatch']
        self.assertEqual({item['field'] for item in mismatches}, {'total_time', 'last_30'})
        self.assertEqual({item['scope'] for item in mismatches}, {'lifetime', 'rolling'})
        self.assertFalse(report['records_changed'])
        for model in (Aircraft, Flight, Imported, Total, Stat):
            self.assertEqual(before[model.__name__], list(model.objects.order_by('pk').values()))
        self.assertEqual(report['snapshots'], self.report()['snapshots'])

    def test_reports_incomplete_classifications_without_rejecting_legacy_aircraft(self):
        blank = Aircraft.objects.create(user=self.user, aircraft_type='IMPORTED')
        bad = Aircraft.objects.create(user=self.user, aircraft_type='MISMATCH',
            aircraft_category='A', aircraft_class='HELO', turbine=True, piston=True, small=True, heavy=True)
        findings = {row['id']: row['findings'] for row in self.report()['aircraft']}
        self.assertEqual(set(findings[blank.pk]),
            {'category_not_recorded', 'class_not_recorded', 'engine_not_recorded', 'weight_not_recorded'})
        self.assertEqual(set(findings[bad.pk]),
            {'category_class_mismatch', 'multiple_engines_selected', 'multiple_weights_selected'})
        self.assertEqual(Aircraft.objects.get(pk=blank.pk).aircraft_category, '')

    def test_missing_and_unsupported_summary_rows_are_reported_not_created(self):
        Stat.objects.filter(user=self.user).delete()
        Total.objects.filter(user=self.user, total='ASEL').delete()
        Total.objects.create(user=self.user, total='Legacy')
        report = self.report()
        missing = {(row['model'], row['group']) for row in report['issues'] if row['kind'] == 'missing_summary'}
        self.assertEqual(missing, {('Stat', 'C172'), ('Total', 'ASEL')})
        self.assertTrue(any(row['kind'] == 'unsupported_summary' for row in report['issues']))
        self.assertFalse(Stat.objects.filter(user=self.user).exists())

    def test_legacy_uppercase_all_is_supported_and_normalized_duplicates_are_reported(self):
        Total.objects.filter(user=self.user, total='All').update(total='ALL')
        self.assertEqual(self.report()['issues'], [])
        Total.objects.create(user=self.user, total='All')
        duplicates = [item for item in self.report()['issues'] if item['kind'] == 'duplicate_summary']
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]['group'], 'All')

    def test_account_filter_and_preserved_raw_summary_nulls(self):
        other = get_user_model().objects.create_user(username='other-classification-audit')
        Aircraft.objects.create(user=other, aircraft_type='PRIVATE')
        Total.objects.filter(user=self.user, total='All').update(instrument=None)
        report = self.report(user_id=self.user.pk)
        self.assertEqual(report['snapshots']['Aircraft']['count'], 1)
        self.assertEqual({row['user_id'] for row in report['aircraft']}, {self.user.pk})
        self.assertEqual(report['issues'], [])  # Null numeric equals zero only for comparison.
        all_row = next(row for row in report['stored_summaries']['Total'] if row['total'] == 'All')
        self.assertIsNone(all_row['instrument'])


class ClassificationAuditCommandTests(TransactionTestCase):
    def test_postgres_read_only_snapshot_and_private_nonoverwriting_output(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Command requires PostgreSQL snapshot support.')
        statements = []

        def record(execute, sql, params, many, context):
            statements.append(sql)
            return execute(sql, params, many, context)

        with TemporaryDirectory() as directory:
            output = Path(directory) / 'baseline.json'
            with connection.execute_wrapper(record):
                call_command('audit_aircraft_classifications', output=output, as_of=date(2026, 11, 24), stdout=StringIO())
            report = json.loads(output.read_text())
            self.assertFalse(report['records_changed'])
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertTrue(any('REPEATABLE READ, READ ONLY' in sql for sql in statements))
            self.assertFalse(any(sql.lstrip().split()[0].upper() in ('INSERT', 'UPDATE', 'DELETE') for sql in statements))
            saved = output.read_bytes()
            with self.assertRaises(CommandError):
                call_command('audit_aircraft_classifications', output=output, stdout=StringIO())
            self.assertEqual(output.read_bytes(), saved)
