import datetime
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from flights.models import Aircraft, Flight, TailNumber
from home.currency import medical_duration, type_currency


class CurrencyRolloverTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='currency_rollover')
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='B737', requires_type=True)
        self.tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N123A')
        self.as_of = date(2028, 1, 1)

    def flight(self, day):
        Flight.objects.bulk_create([Flight(user=self.user, aircraft_type=self.aircraft,
            registration=self.tail, date=day, duration=1, route='KAAA-KBBB', landings_day=3, landings_night=3)])

    def current_at(self, day):
        with patch('home.currency.datetime', wraps=datetime) as clock:
            clock.date.today.return_value = day
            return type_currency(self.user)

    def test_type_currency_changes_after_midnight_without_process_restart(self):
        self.flight(self.as_of - timedelta(days=90))
        self.assertEqual(self.current_at(self.as_of)['B737'], (3, True, 3, True))
        self.assertEqual(self.current_at(self.as_of + timedelta(days=1))['B737'], (0, False, 0, False))

    def test_two_year_cutoff_and_future_flights_are_evaluated_on_each_call(self):
        self.flight(self.as_of - timedelta(days=730))
        self.assertIn('B737', self.current_at(self.as_of))
        self.assertEqual(self.current_at(self.as_of + timedelta(days=1)), {})
        self.flight(self.as_of + timedelta(days=5))
        self.assertEqual(self.current_at(self.as_of + timedelta(days=1)), {})

    def test_unset_medical_fallback_uses_current_request_date(self):
        for day in (self.as_of, self.as_of + timedelta(days=1)):
            with patch('home.currency.datetime', wraps=datetime) as clock:
                clock.date.today.return_value = day
                self.assertEqual(medical_duration(self.user)[0], day - timedelta(days=1))
