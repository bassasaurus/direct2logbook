from datetime import date
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from api.serializers import FlightSerializer
from flights.mileage import route_distance_nm
from flights.models import Aircraft, Flight, MapData, TailNumber


class RouteMileageTests(SimpleTestCase):
    def flight(self, points, route='AAA-BBB'):
        return SimpleNamespace(route=route, route_data=[
            SimpleNamespace(latitude=lat, longitude=lon) for lat, lon in points])

    def test_equatorial_degree_and_each_leg_of_round_trip(self):
        self.assertEqual(route_distance_nm(self.flight([(0, 0), (0, 1)])), 60.0)
        self.assertEqual(route_distance_nm(self.flight([(0, 0), (0, 1), (0, 0)], 'AAA-BBB-AAA')), 120.1)

    def test_date_line_uses_short_path(self):
        self.assertAlmostEqual(route_distance_nm(self.flight([(0, 179), (0, -179)])), 120.1, places=1)

    def test_unresolved_and_invalid_coordinates_do_not_report_partial_distance(self):
        for points in ([], [(0, 0)], [(0, 0), (91, 0)], [(0, 0), (float('nan'), 0)]):
            self.assertIsNone(route_distance_nm(self.flight(points)))

    def test_local_flight_and_repeated_airports_have_zero_distance(self):
        self.assertEqual(route_distance_nm(self.flight([(0, 0)], 'AAA')), 0.0)
        self.assertEqual(route_distance_nm(self.flight([(0, 0), (0, 0)])), 0.0)


@override_settings(SECURE_SSL_REDIRECT=False)
class FlightMileageDisplayTests(TestCase):
    def test_api_and_detail_share_read_only_distance_and_route_edits_recalculate(self):
        user = get_user_model().objects.create_user(username='mileage')
        user.profile.active = True
        user.profile.save(update_fields=['active'])
        aircraft = Aircraft.objects.create(user=user, aircraft_type='C172')
        tail = TailNumber.objects.create(user=user, aircraft=aircraft, registration='N172')
        for code, longitude in [('KAAA', 0), ('KBBB', 1)]:
            MapData.objects.create(icao=code, name=code, country='United States', latitude=0, longitude=longitude)
        flight = Flight.objects.create(user=user, aircraft_type=aircraft, registration=tail,
                                      route='KAAA-KBBB', date=date(2026, 1, 1), duration=1, pilot_in_command=True)
        flight.refresh_from_db()
        self.assertEqual(FlightSerializer(flight).data['distance_nm'], 60.0)
        self.assertTrue(FlightSerializer().fields['distance_nm'].read_only)
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse('flight_detail', args=[flight.pk])), '60.0 NM')
        flight.route = 'KAAA-KBBB-KAAA'
        flight.save()
        flight.refresh_from_db()
        self.assertEqual(flight.distance_nm, 120.1)
        flight.route = 'KAAA-UNKNOWN-KBBB'
        flight.save()
        flight.refresh_from_db()
        self.assertIsNone(FlightSerializer(flight).data['distance_nm'])
        self.assertContains(self.client.get(reverse('flight_detail', args=[flight.pk])), 'Mileage unavailable')
