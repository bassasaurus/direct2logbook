from datetime import date
from types import SimpleNamespace
from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse

from flights.map_routes import flight_map_data
from flights.models import Flight, Aircraft, TailNumber, MapData


class FlightMapDataTests(SimpleTestCase):
    def test_keeps_independent_routes_and_deduplicates_only_consecutive_points(self):
        a = SimpleNamespace(pk=1, latitude=10, longitude=20)
        b = SimpleNamespace(pk=2, latitude=30, longitude=40)
        c = SimpleNamespace(pk=3, latitude=50, longitude=60)
        data = flight_map_data([
            SimpleNamespace(pk=10, route_data=[a, a, b, a]),
            SimpleNamespace(pk=11, route_data=[b, c]),
        ])
        self.assertEqual(data['routes']['10'], [[10, 20], [30, 40], [10, 20]])
        self.assertEqual(data['routes']['11'], [[30, 40], [50, 60]])
        self.assertEqual(len(data['airports']['features']), 3)
        self.assertEqual(data['airports']['features'][0]['geometry']['coordinates'], [20, 10])

    def test_missing_and_invalid_coordinates_are_safe(self):
        invalid = [None, SimpleNamespace(latitude=None, longitude=20),
                   SimpleNamespace(latitude=float('nan'), longitude=20),
                   SimpleNamespace(latitude=95, longitude=20)]
        data = flight_map_data([SimpleNamespace(pk=10, route_data=invalid),
                                SimpleNamespace(pk=11, route_data=None)])
        self.assertEqual(data['routes'], {'10': [], '11': []})
        self.assertEqual(data['airports']['features'], [])


@override_settings(SECURE_SSL_REDIRECT=False)
class MonthlyMapOwnershipTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='monthly_map')
        self.other = get_user_model().objects.create_user(username='monthly_map_other')
        self.user.profile.active = True
        self.user.profile.expired = False
        self.user.profile.save()
        self.client.force_login(self.user)
        self.a = MapData.objects.create(country='United States', icao='KAAA', iata='AAA', latitude=10, longitude=20)
        self.b = MapData.objects.create(country='United States', icao='KBBB', iata='BBB', latitude=30, longitude=40)

    def flight(self, user, day):
        aircraft, _ = Aircraft.objects.get_or_create(user=user, aircraft_type='C172')
        registration, _ = TailNumber.objects.get_or_create(user=user, registration='N726T', defaults={'aircraft': aircraft})
        return Flight.objects.create(user=user, date=day, aircraft_type=aircraft,
                                      registration=registration, route='KAAA-KBBB', duration=1)

    def test_monthly_map_contains_only_visible_owned_flights(self):
        current = self.flight(self.user, date(2025, 1, 15))
        foreign = self.flight(self.other, date(2025, 1, 15))
        other_month = self.flight(self.user, date(2025, 2, 15))
        response = self.client.get(reverse('flight_by_month', kwargs={'year': 2025, 'month': 'jan'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.context['flight_map']['routes']), {str(current.pk)})
        self.assertContains(response, f'data-flight-id="{current.pk}"')
        self.assertNotContains(response, f'data-flight-id="{foreign.pk}"')
        self.assertNotContains(response, f'data-flight-id="{other_month.pk}"')
        self.assertContains(response, 'id="flight-map-data"')
        self.assertContains(response, 'flight_route_highlight.js')
        self.assertNotContains(response, f'/flights/geojson/routes/{self.user.pk}/')
        self.assertEqual(response.context['flight_map']['routes'][str(current.pk)], [[10, 20], [30, 40]])
