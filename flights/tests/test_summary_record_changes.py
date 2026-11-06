from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from flights.models import Aircraft, Flight, Imported, Stat, TailNumber, Total
from flights.rolling_stats import ROLLING_FIELDS


class SummaryRecordChangeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='summary-changes')
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='C172', aircraft_category='A', aircraft_class='SEL')
        self.tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='NCHNG')
        self.today = date(2026, 11, 6)
        self.clock = patch('flights.rolling_stats.timezone.localdate', return_value=self.today)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def flight(self, day=None, duration='2.5'):
        return Flight.objects.create(user=self.user, aircraft_type=self.aircraft, registration=self.tail,
                                     date=day or self.today, duration=duration, route='IAH-LAX')

    def test_delete_removes_flight_from_every_rolling_column_immediately(self):
        self.flight(self.today - timedelta(days=1), '1.5')
        deleted = self.flight()
        deleted.delete()
        stat = Stat.objects.get(user=self.user, aircraft_type='C172')
        total = Total.objects.get(user=self.user, total='All')
        for summary in (stat, total):
            for field in ROLLING_FIELDS:
                self.assertEqual(getattr(summary, field), self.today - timedelta(days=1) if field == 'last_flown' else Decimal('1.5'))

    def test_deleting_last_dated_flight_keeps_imported_lifetime_but_clears_windows(self):
        Imported.objects.create(user=self.user, aircraft_type=self.aircraft, total_time='100', last_flown=date(2020, 1, 1))
        flight = self.flight()
        flight.delete()
        stat = Stat.objects.get(user=self.user, aircraft_type='C172')
        self.assertEqual(stat.total_time, Decimal('100'))
        self.assertEqual(stat.last_flown, date(2020, 1, 1))
        for field in ROLLING_FIELDS:
            if field != 'last_flown': self.assertEqual(getattr(stat, field), 0)

    def test_deleting_imported_balance_preserves_remaining_dated_flights(self):
        self.flight()
        imported = Imported.objects.create(user=self.user, aircraft_type=self.aircraft, total_time='100')
        imported.delete()
        stat = Stat.objects.get(user=self.user, aircraft_type='C172')
        self.assertEqual(stat.total_time, Decimal('2.5'))
        self.assertEqual(stat.last_30, Decimal('2.5'))

    def test_changing_aircraft_recalculates_both_old_and_new_stats(self):
        self.flight(duration='1.0')
        changed = self.flight()
        other = Aircraft.objects.create(user=self.user, aircraft_type='PA28', aircraft_category='A', aircraft_class='SEL')
        tail = TailNumber.objects.create(user=self.user, aircraft=other, registration='NNEW')
        changed.aircraft_type = other
        changed.registration = tail
        changed.save()
        old = Stat.objects.get(user=self.user, aircraft_type='C172')
        new = Stat.objects.get(user=self.user, aircraft_type='PA28')
        self.assertEqual(old.last_30, Decimal('1.0'))
        self.assertEqual(new.last_30, Decimal('2.5'))
        self.assertEqual(old.total_time, Decimal('1.0'))

    def test_no_empty_stat_after_last_flight_is_deleted(self):
        self.flight().delete()
        self.assertFalse(Stat.objects.filter(user=self.user, aircraft_type='C172').exists())

    def test_date_change_recalculates_rolling_windows_without_affecting_lifetime(self):
        flight = self.flight()
        flight.date = self.today - timedelta(days=731)
        flight.save()
        for summary in (Stat.objects.get(user=self.user, aircraft_type='C172'),
                        Total.objects.get(user=self.user, total='All')):
            self.assertEqual(summary.total_time, Decimal('2.5'))
            for field in ROLLING_FIELDS:
                if field != 'last_flown': self.assertEqual(getattr(summary, field), 0)
