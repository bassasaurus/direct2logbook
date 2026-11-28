from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.template.loader import render_to_string
from django.urls import reverse
from rest_framework.test import APIClient

from flights.models import Aircraft, Flight, TailNumber
from home.passenger_currency import landing_status, passenger_currency


@override_settings(SECURE_SSL_REDIRECT=False)
class PassengerCurrencyTests(TestCase):
    today = date(2026, 11, 30)

    def setUp(self):
        self.user = get_user_model().objects.create_user('passenger-recency')
        self.user.profile.free_access = True
        self.user.profile.save(update_fields=['free_access'])
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='C172', aircraft_category='A', aircraft_class='SEL')
        self.tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N123', is_91=True)

    def flight(self, *, days=0, aircraft=None, **values):
        aircraft = aircraft or self.aircraft
        tail = self.tail if aircraft.pk == self.aircraft.pk else TailNumber.objects.create(user=self.user, aircraft=aircraft, registration=f'N{aircraft.pk}X', is_91=True)
        return Flight.objects.bulk_create([Flight(user=self.user, aircraft_type=aircraft, registration=tail,
            date=self.today-timedelta(days=days), route='IAH-IAH', duration='1.0', **values)])[0]

    def snapshot(self):
        return passenger_currency(self.user, today=self.today)

    def test_three_night_full_stop_landings_satisfy_both_day_and_night(self):
        self.flight(days=10, landings_night=3, night_landings_full_stop=True, night='.5')
        row = self.snapshot()['categories'][0]
        for status in (row['day'], row['night']):
            self.assertEqual(status['count'], 3)
            self.assertTrue(status['current'])
            self.assertEqual(status['last_dates'], [self.today-timedelta(days=10)]*3)
            self.assertEqual(status['valid_through'], self.today+timedelta(days=80))

    def test_night_without_confirmed_full_stop_counts_only_toward_day(self):
        for marker in (None, False):
            self.flight(landings_night=2, night_landings_full_stop=marker)
        row = self.snapshot()['categories'][0]
        self.assertEqual(row['day']['count'], 4)
        self.assertTrue(row['day']['current'])
        self.assertEqual(row['night']['count'], 0)
        self.assertFalse(row['night']['current'])

    def test_last_three_use_earliest_of_the_latest_three_not_the_oldest_flight(self):
        self.flight(days=80, landings_day=4)
        self.flight(days=20, landings_day=2)
        self.flight(days=5, landings_night=1)
        status = self.snapshot()['categories'][0]['day']
        self.assertEqual(status['last_dates'], [self.today-timedelta(days=5), self.today-timedelta(days=20), self.today-timedelta(days=20)])
        self.assertEqual(status['valid_through'], self.today+timedelta(days=70))
        self.assertEqual(status['count'], 7)

    def test_expired_rows_keep_the_last_three_dates_and_their_expiry(self):
        self.flight(days=100, landings_night=3, night_landings_full_stop=True)
        row = self.snapshot()['categories'][0]
        for status in (row['day'], row['night']):
            self.assertEqual(status['count'], 0)
            self.assertFalse(status['current'])
            self.assertEqual(status['last_dates'], [self.today-timedelta(days=100)]*3)
            self.assertEqual(status['valid_through'], self.today-timedelta(days=10))
            html = render_to_string('home/passenger_landing_cell.html', {'status': status, 'currency_row': True})
            self.assertIn('Expired Nov 20, 2026', html)
            self.assertNotIn('0/3', html)
            self.assertNotIn('Log 3 more', html)
            self.assertNotIn('Aug 22', html)

    def test_partial_three_has_no_currency_date(self):
        self.flight(landings_day=2)
        status = self.snapshot()['categories'][0]['day']
        self.assertFalse(status['current'])
        self.assertEqual(status['still_needed'], 1)
        self.assertIsNone(status['valid_through'])

    def test_90_day_boundary_and_simulator_future_and_other_account_exclusions(self):
        self.flight(days=90, landings_day=3)
        self.flight(days=91, landings_day=20)
        self.flight(days=-1, landings_day=20)
        self.flight(landings_day=20, simulator=True)
        status = self.snapshot()['categories'][0]['day']
        self.assertEqual(status['count'], 3)
        self.assertEqual(status['valid_through'], self.today)
        tomorrow = landing_status(Flight.objects.filter(user=self.user).exclude(date__gt=self.today), today=self.today+timedelta(days=1))
        self.assertEqual(tomorrow['count'], 0)

    def test_web_and_mobile_share_dates_and_show_seaplane_and_helicopter_rows(self):
        self.flight(landings_day=3)
        for category, klass, designator in [('A','SES','C172F'),('R','HELO','R44')]:
            aircraft = Aircraft.objects.create(user=self.user, aircraft_type=designator, aircraft_category=category, aircraft_class=klass)
            self.flight(aircraft=aircraft, landings_day=3)
        api = APIClient()
        api.force_authenticate(self.user)
        self.client.force_login(self.user)
        with patch('home.passenger_currency.timezone.localdate', return_value=self.today):
            response = api.get('/api/mobile/recency/')
            home = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['categories'], home.context['passenger_categories'])
        self.assertEqual([r['label'] for r in response.data['categories']], ['ASEL','ASES','HELO'])
        self.assertContains(home, 'Passenger Currency')
        self.assertContains(home, 'Until Feb 28, 2027')

    def test_currency_row_separates_status_and_expiry_from_landing_counts(self):
        self.flight(landings_day=3, days=10)
        row = self.snapshot()['categories'][0]
        counts = render_to_string('home/passenger_landing_cell.html', {'status': row['day']})
        currency = render_to_string('home/passenger_landing_cell.html', {'status': row['day'], 'currency_row': True})
        self.assertIn('3/3', counts)
        self.assertNotIn('Until', counts)
        self.assertIn('Until Feb 18, 2027', currency)
        self.assertNotIn('3/3', currency)
        missing = render_to_string('home/passenger_landing_cell.html', {'status': row['night'], 'currency_row': True})
        self.assertIn('Not current', missing)
        for template, context in [('home/vfr_currency.html', {'passenger_categories': [row]}),
                                  ('home/type_currency.html', {'passenger_types': [row]})]:
            html = render_to_string(template, context)
            self.assertIn('<th scope="row">Currency</th>', html)
            self.assertIn('Until Feb 18, 2027', html)
