from contextlib import ExitStack
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from flights.models import Aircraft, Flight, Imported, TailNumber
from home import views


CURRENCY_NAMES = [f'{category}_vfr_{period}' for category in
                  ('asel', 'amel', 'ases', 'ames', 'helo', 'gyro') for period in ('day', 'night')]


@override_settings(SECURE_SSL_REDIRECT=False)
class DashboardPerformanceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='dashboard_owner')
        self.other = get_user_model().objects.create_user(username='dashboard_other')
        profile = self.user.profile
        profile.active = True
        profile.expired = False
        profile.first_class = True
        profile.over_40 = False
        profile.medical_issue_date = date.today()
        profile.save()
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='C172',
                                               aircraft_category='A', aircraft_class='SEL')
        self.tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N123A')
        self.flights = Flight.objects.bulk_create([
            Flight(user=self.user, aircraft_type=self.aircraft, registration=self.tail,
                   date=date.today() - timedelta(days=1), route='KAAA-KBBB', duration=1,
                   landings_day=1, landings_night=1)
            for index in range(3)
        ])
        Flight.objects.bulk_create([
            Flight(user=self.other, aircraft_type=self.aircraft, registration=self.tail,
                   date=date.today(), route='PRIVATE-ROUTE', duration=1, landings_day=10, landings_night=10)
        ])
        self.client.force_login(self.user)

    def test_currency_helpers_run_once_and_preserve_results(self):
        with ExitStack() as stack:
            helpers = {name: stack.enter_context(patch('home.views.' + name, wraps=getattr(views, name)))
                       for name in CURRENCY_NAMES + ['medical_duration']}
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        print(f'Home dashboard (3 flights, 1 aircraft): {len(queries)} queries')
        for name, helper in helpers.items():
            with self.subTest(helper=name):
                self.assertEqual(helper.call_count, 1)
        for name in CURRENCY_NAMES:
            self.assertEqual(response.context[name], 3 if name.startswith('asel_') else 0)
            self.assertEqual(response.context[name + '_current'], name.startswith('asel_'))
        self.assertTrue(response.context['current'])
        self.assertNotContains(response, 'PRIVATE-ROUTE')
        self.assertFalse(response.context['new_user_flight'])
        self.assertFalse(response.context['new_user_aircraft'])
        self.assertFalse(response.context['new_user_tailnumber'])

    def test_more_aircraft_do_not_add_per_aircraft_queries(self):
        self.client.get(reverse('home'))  # Warm Site/template caches before comparing.
        with CaptureQueriesContext(connection) as first:
            response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        aircraft = Aircraft.objects.bulk_create([
            Aircraft(user=self.user, aircraft_type=f'X{index:03d}') for index in range(20)
        ])
        with CaptureQueriesContext(connection) as second:
            response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        print(f'Home queries: 1 aircraft={len(first)}, 21 aircraft={len(second)}')
        self.assertEqual(len(second), len(first))
        self.assertEqual({a.pk for a in response.context['aircraft_needs_tailnumber']},
                         {a.pk for a in aircraft})

    def test_missing_aircraft_details_respect_registration_imports_and_owner(self):
        imported = Aircraft.objects.create(user=self.user, aircraft_type='IMP1')
        missing = Aircraft.objects.create(user=self.user, aircraft_type='MISS')
        Imported.objects.bulk_create([
            Imported(user=self.user, aircraft_type=imported, total_time=1),
            Imported(user=self.other, aircraft_type=missing, total_time=1),
        ])
        TailNumber.objects.create(user=self.other, aircraft=missing, registration='N999A')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([aircraft.pk for aircraft in response.context['aircraft_needs_tailnumber']],
                         [missing.pk])

    def test_empty_account_still_gets_onboarding_flags(self):
        user = get_user_model().objects.create_user(username='empty_dashboard')
        user.profile.trial = True
        user.profile.save()
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        for name in ('new_user_aircraft', 'new_user_tailnumber', 'new_user_flight'):
            self.assertTrue(response.context[name])
