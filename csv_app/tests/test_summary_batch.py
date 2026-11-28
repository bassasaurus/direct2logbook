from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from csv_app.csv_import import csv_import
from csv_app.tests.airport_fixtures import seed_airports
from csv_app.tests.record_fixtures import seed_records
from csv_app.tests.test_atomic_import import content, row
from flights.models import Aircraft, Flight, Stat, TailNumber, Total
from flights.summary_batch import batch_flight_summaries, defer_flight_summary


class CSVSummaryBatchTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('batched-import')
        self.aircraft, self.tail = seed_records(self.user)
        seed_airports()
        self.request = SimpleNamespace(user=self.user)

    def test_multi_category_import_commits_matching_summaries_and_maps(self):
        aircraft = Aircraft.objects.create(user=self.user, aircraft_type='B737',
            aircraft_category='A', aircraft_class='MEL', turbine=True, large=True)
        TailNumber.objects.create(user=self.user, aircraft=aircraft, registration='N737TS', is_121=True)
        from django.db.models.signals import post_save
        observed = []
        def observe(sender, instance, **kwargs):
            observed.append(Total.objects.get(user=self.user, total='All').total_time)
        post_save.connect(observe, sender=Flight)
        self.addCleanup(post_save.disconnect, observe, sender=Flight)
        result = csv_import.run(self.request, content([
            row(), row(**{'1':'B737','2':'N737TS','5':'0','6':'1.5'}), row(),
        ]))
        self.assertEqual(result, 3)
        self.assertEqual(observed, [Decimal('0')] * 3)
        self.assertEqual(Total.objects.get(user=self.user,total='All').total_time, Decimal('4.5'))
        self.assertEqual(Total.objects.get(user=self.user,total='ASEL').total_time, Decimal('3.0'))
        self.assertEqual(Total.objects.get(user=self.user,total='AMEL').total_time, Decimal('1.5'))
        self.assertEqual(Stat.objects.get(user=self.user,aircraft_type='C172').total_time, Decimal('3.0'))
        self.assertEqual(Stat.objects.get(user=self.user,aircraft_type='B737').second_in_command, Decimal('1.5'))
        for flight in Flight.objects.filter(user=self.user):
            self.assertTrue(flight.route_data)
            self.assertTrue(flight.app_markers)
            self.assertFalse(flight.aircraft_type_error)
            self.assertFalse(flight.registration_error)
            self.assertEqual(flight.approach_set.get().number, 2)

    def test_summary_write_count_does_not_grow_with_import_rows(self):
        csv_import.run(self.request, content())  # Create all relevant summary rows first.
        def summary_writes(count):
            with CaptureQueriesContext(connection) as queries:
                csv_import.run(self.request, content([row()] * count))
            tables = ('total','stat','regs','power','weight','endorsement')
            return sum(any(query['sql'].startswith(f'{operation} "flights_{table}"')
                           for operation in ('UPDATE','INSERT INTO','DELETE FROM') for table in tables)
                       for query in queries.captured_queries)
        single = summary_writes(1)
        many = summary_writes(20)
        self.assertGreater(single, 0)
        self.assertEqual(single, many)
        self.assertEqual(Flight.objects.filter(user=self.user).count(), 22)
        self.assertEqual(Total.objects.get(user=self.user,total='All').total_time, Decimal('33.0'))

    def test_rebuild_failure_rolls_back_flights_and_restores_normal_signals(self):
        original = list(Total.objects.filter(user=self.user).values())
        with patch('flights.summary_batch.rebuild_flight_summaries', side_effect=RuntimeError('rebuild failed')):
            with self.assertRaisesRegex(RuntimeError, 'rebuild failed'):
                csv_import.run(self.request, content([row(),row()]))
        self.assertFalse(Flight.objects.filter(user=self.user).exists())
        self.assertEqual(list(Total.objects.filter(user=self.user).values()), original)
        # An ordinary save after failure still updates summaries immediately.
        flight = Flight.objects.create(user=self.user, aircraft_type=self.aircraft,
            registration=self.tail, date='2026-11-26', route='KIAH-KMCO',
            duration='1.0',pilot_in_command=True)
        self.assertEqual(Total.objects.get(user=self.user,total='All').total_time, Decimal('1.0'))
        self.assertTrue(Flight.objects.filter(pk=flight.pk).exists())

    def test_batch_is_isolated_from_other_accounts_and_execution_threads(self):
        other = get_user_model().objects.create_user('unrelated-batch')
        flight = Flight(user=self.user, aircraft_type=self.aircraft)
        with transaction.atomic(), patch('flights.summary_batch.rebuild_flight_summaries') as rebuild:
            with batch_flight_summaries(self.user):
                self.assertTrue(defer_flight_summary(flight))
                self.assertFalse(defer_flight_summary(Flight(user=other,aircraft_type=self.aircraft)))
                with ThreadPoolExecutor(max_workers=1) as pool:
                    self.assertFalse(pool.submit(defer_flight_summary,flight).result(timeout=5))
            rebuild.assert_called_once_with(self.user, {self.aircraft.pk})
        self.assertFalse(defer_flight_summary(flight))
