from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from flights.models import Aircraft, Flight, Imported, Stat, TailNumber, Total
from flights.rolling_stats import refresh_rolling_stats, rolling_values
from flights.signal_stat import stat_update
from flights.signal_total import total_all_update


class RollingStatisticsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='rolling_owner')
        self.other = get_user_model().objects.create_user(username='rolling_other')
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='C172',
                                               aircraft_category='A', aircraft_class='SEL')
        self.tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N123A')
        self.as_of = date(2028, 1, 1)
        self.stat = Stat.objects.create(user=self.user, aircraft_type='C172', total_time=100,
                                       pilot_in_command=75, last_30=99, ytd=99)
        self.total = Total.objects.get(user=self.user, total='All')
        Total.objects.filter(pk=self.total.pk).update(total_time=100, pilot_in_command=75, last_30=99, ytd=99)

    def flight(self, day, duration='2.5', user=None, aircraft=None, **kwargs):
        return Flight.objects.bulk_create([Flight(
            user=user or self.user, aircraft_type=aircraft or self.aircraft, registration=self.tail,
            date=day, duration=Decimal(duration), route='KAAA-KBBB', **kwargs,
        )])[0]

    def values(self, as_of, flights=None):
        return rolling_values(flights if flights is not None else Flight.objects.filter(user=self.user),
                              Imported.objects.filter(user=self.user), as_of)

    def test_all_six_windows_age_out_after_inclusive_boundary(self):
        for field, days in [('last_30', 30), ('last_60', 60), ('last_90', 90),
                            ('last_180', 180), ('last_yr', 365), ('last_2yr', 730)]:
            with self.subTest(window=field):
                flight = self.flight(self.as_of - timedelta(days=days))
                source = Flight.objects.filter(pk=flight.pk)
                self.assertEqual(self.values(self.as_of, source)[field], Decimal('2.5'))
                self.assertEqual(self.values(self.as_of + timedelta(days=1), source)[field], 0)

    def test_new_year_and_future_flights_advance_without_editing(self):
        self.flight(date(2027, 12, 31), '2.5')
        self.flight(date(2028, 1, 1), '3.5')
        previous = self.values(date(2027, 12, 31))
        current = self.values(date(2028, 1, 1))
        self.assertEqual(previous['ytd'], Decimal('2.5'))
        self.assertEqual(previous['last_flown'], date(2027, 12, 31))
        self.assertEqual(current['ytd'], Decimal('3.5'))
        self.assertEqual(current['last_30'], Decimal('6.0'))
        self.assertEqual(current['last_flown'], date(2028, 1, 1))

    def test_historical_last_flown_is_used_but_undated_windows_are_not(self):
        Imported.objects.bulk_create([Imported(user=self.user, aircraft_type=self.aircraft,
            total_time=100, last_flown=date(2027, 12, 15), last_30=99, last_60=99,
            last_90=99, last_180=99, last_yr=99, last_2yr=99, ytd=99)])
        values = self.values(self.as_of)
        self.assertEqual(values.pop('last_flown'), date(2027, 12, 15))
        self.assertTrue(all(value == 0 for value in values.values()))
        refresh_rolling_stats(self.as_of, user_id=self.user.pk)
        for summary in (self.stat, self.total):
            summary.refresh_from_db()
            self.assertEqual(summary.total_time, Decimal('100'))
            self.assertEqual(summary.pilot_in_command, Decimal('75'))
            self.assertEqual(summary.last_flown, date(2027, 12, 15))
        imported = Imported.objects.get(user=self.user)
        self.assertEqual(imported.last_30, Decimal('99'))  # Source input is not destroyed.

    def test_command_refreshes_both_tables_and_is_safe_to_repeat(self):
        self.flight(self.as_of - timedelta(days=30))
        with patch('flights.management.commands.refresh_rolling_stats.timezone.localdate', return_value=self.as_of):
            call_command('refresh_rolling_stats', stdout=StringIO())
        for summary in (self.stat, self.total):
            summary.refresh_from_db()
            self.assertEqual(summary.last_30, Decimal('2.5'))
            self.assertEqual(summary.total_time, Decimal('100'))
        tomorrow = self.as_of + timedelta(days=1)
        first = refresh_rolling_stats(tomorrow)
        second = refresh_rolling_stats(tomorrow)
        self.assertEqual(first, second)
        for summary in (self.stat, self.total):
            summary.refresh_from_db()
            self.assertEqual(summary.last_30, 0)
            self.assertEqual(summary.last_60, Decimal('2.5'))

    def test_owner_aircraft_and_category_isolation(self):
        self.flight(self.as_of)
        self.flight(self.as_of, '20', user=self.other)
        rotor = Aircraft.objects.create(user=self.user, aircraft_type='R44',
                                        aircraft_category='R', aircraft_class='HELO')
        self.flight(self.as_of, '3.5', aircraft=rotor)
        rotor_stat = Stat.objects.create(user=self.user, aircraft_type='R44')
        asel = Total.objects.create(user=self.user, total='ASEL')
        helo = Total.objects.create(user=self.user, total='HELO')
        refresh_rolling_stats(self.as_of, user_id=self.user.pk)
        for summary, expected in [(self.stat, '2.5'), (rotor_stat, '3.5'),
                                  (self.total, '6.0'), (asel, '2.5'), (helo, '3.5')]:
            summary.refresh_from_db()
            self.assertEqual(summary.last_30, Decimal(expected))

    def test_dry_run_does_not_save(self):
        self.flight(self.as_of)
        result = refresh_rolling_stats(self.as_of, dry_run=True)
        self.assertGreater(result['stats'], 0)
        self.stat.refresh_from_db()
        self.total.refresh_from_db()
        self.assertEqual(self.stat.last_30, Decimal('99'))
        self.assertEqual(self.total.last_30, Decimal('99'))

    def test_save_handlers_use_same_policy_for_historical_totals(self):
        flight = self.flight(self.as_of)
        Imported.objects.bulk_create([Imported(user=self.user, aircraft_type=self.aircraft,
            total_time=100, last_flown=self.as_of - timedelta(days=1), last_30=99, ytd=99)])
        with patch('flights.rolling_stats.timezone.localdate', return_value=self.as_of):
            stat_update(Flight, flight)
            total_all_update(Flight, flight)
        for summary in (self.stat, self.total):
            summary.refresh_from_db()
            self.assertEqual(summary.total_time, Decimal('102.5'))
            self.assertEqual(summary.last_30, Decimal('2.5'))
            self.assertEqual(summary.ytd, Decimal('2.5'))
            self.assertEqual(summary.last_flown, self.as_of)

    def test_missing_or_null_last_dates_are_none_not_1900(self):
        Imported.objects.bulk_create([Imported(user=self.user, aircraft_type=self.aircraft, total_time=10)])
        self.assertIsNone(self.values(self.as_of)['last_flown'])

    def test_legacy_uppercase_and_padded_known_categories_refresh_normally(self):
        self.flight(self.as_of)
        rows = [Total.objects.create(user=self.user, total=label, total_time=100, last_30=99)
                for label in ('ALL', ' all ', 'asel', ' ASEL ')]
        result = refresh_rolling_stats(self.as_of, user_id=self.user.pk)
        self.assertEqual(result['skipped_total_ids'], [])
        for row in rows:
            label = row.total
            row.refresh_from_db()
            self.assertEqual(row.last_30, Decimal('2.5'))
            self.assertEqual(row.total_time, Decimal('100'))
            self.assertEqual(row.total, label)  # Don't rewrite or merge historical rows.

    def test_unknown_categories_are_reported_and_preserved_without_blocking_users(self):
        self.flight(self.as_of)
        unknown = Total.objects.create(user=self.user, total='Legacy custom', last_30=99)
        result = refresh_rolling_stats(self.as_of)
        self.assertEqual(result['skipped_total_ids'], [unknown.pk])
        unknown.refresh_from_db()
        self.total.refresh_from_db()
        self.stat.refresh_from_db()
        other_total = Total.objects.get(user=self.other, total='All')
        self.assertEqual(unknown.last_30, Decimal('99'))
        self.assertEqual(self.total.last_30, Decimal('2.5'))
        self.assertEqual(self.stat.last_30, Decimal('2.5'))
        self.assertEqual(other_total.last_30, 0)

    def test_dry_run_reports_unknown_categories_without_writes(self):
        unknown = Total.objects.create(user=self.user, total='', last_30=99)
        out, errors = StringIO(), StringIO()
        call_command('refresh_rolling_stats', '--dry-run', stdout=out, stderr=errors)
        self.assertIn('Would refresh', out.getvalue())
        self.assertIn('Skipped 1 Total row', errors.getvalue())
        self.assertIn(str(unknown.pk), errors.getvalue())
        self.total.refresh_from_db()
        self.assertEqual(self.total.last_30, Decimal('99'))

    def test_save_handler_also_accepts_legacy_all_and_preserves_unknown_rows(self):
        legacy = Total.objects.create(user=self.user, total='ALL', total_time=99)
        unknown = Total.objects.create(user=self.user, total='Legacy custom', total_time=99)
        flight = self.flight(self.as_of)
        with patch('flights.rolling_stats.timezone.localdate', return_value=self.as_of):
            total_all_update(Flight, flight)
        legacy.refresh_from_db()
        unknown.refresh_from_db()
        self.assertEqual(legacy.total_time, Decimal('2.5'))
        self.assertEqual(legacy.last_30, Decimal('2.5'))
        self.assertEqual(unknown.total_time, Decimal('99'))
