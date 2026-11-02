"""Measure the real list querysets with their rendered templates, using test data."""
from datetime import date
from django.contrib.auth import get_user_model
from django.db import connection
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from flights.models import Aircraft, Approach, Flight, Holding, TailNumber
from flights.views import FlightArchiveMonth, FlightList


class FlightListQueryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='query_owner')
        cls.other = get_user_model().objects.create_user(username='query_other')
        aircraft = Aircraft.objects.create(user=cls.user, aircraft_type='C172')
        tail = TailNumber.objects.create(user=cls.user, aircraft=aircraft, registration='N123A')
        cls.flights = Flight.objects.bulk_create([
            Flight(user=cls.user, date=date(2025, 1, 1), aircraft_type=aircraft,
                   registration=tail, route='KAAA-KBBB', duration=1)
            for index in range(40)
        ])
        Approach.objects.bulk_create([
            Approach(flight_object=flight, approach_type='ILS', number=1) for flight in cls.flights
        ])
        Holding.objects.bulk_create([Holding(flight_object=flight, hold=True) for flight in cls.flights])
        cls.foreign = Flight.objects.bulk_create([
            Flight(user=cls.other, date=date(2025, 1, 1), aircraft_type=aircraft,
                   registration=tail, route='FOREIGN', duration=1)
        ])[0]

    def view(self, view_class):
        view = view_class()
        view.request = RequestFactory().get('/')
        view.request.user = self.user
        return view

    def test_rendering_logbook_has_constant_query_cost(self):
        for size in (1, 40):
            with self.subTest(flights=size):
                view = self.view(FlightList)
                with CaptureQueriesContext(connection) as queries:
                    html = render_to_string('flights/logbook.html',
                                            {'object_list': view.get_queryset()[:size]})
                print(f'Logbook {size} flight(s): {len(queries)} database queries')
                self.assertEqual(len(queries), 3)
                self.assertEqual(html.count('ILS-1'), size)
                self.assertEqual(html.count('<small>| Hold </small>'), size)
                self.assertIn('C172', html)
                self.assertIn('N123A', html)
                self.assertNotIn('FOREIGN', html)

    def test_monthly_queryset_has_no_per_flight_registration_queries(self):
        for size in (1, 40):
            with self.subTest(flights=size):
                view = self.view(FlightArchiveMonth)
                with CaptureQueriesContext(connection) as queries:
                    flights = list(view.get_queryset()[:size])
                    registrations = [str(flight.registration) for flight in flights]
                print(f'Monthly list {size} flight(s): {len(queries)} database queries')
                self.assertEqual(len(queries), 1)
                self.assertEqual(registrations, ['N123A'] * size)
                self.assertNotIn(self.foreign.pk, [flight.pk for flight in flights])
