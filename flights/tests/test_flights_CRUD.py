from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from flights.models import Aircraft, TailNumber, Flight
from datetime import date


class FlightCRUDTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass')

        self.aircraft = Aircraft.objects.create(
            user=self.user,
            aircraft_type='C172',
            turbine=False,
            piston=True,
            requires_type=False,
            tailwheel=False,
            simple=True,
            compleks=False,
            high_performance=False,
            aircraft_category='A',
            aircraft_class='SEL',
            superr=False,
            heavy=False,
            large=False,
            medium=False,
            small=True,
            light_sport=False
        )

        self.tailnumber = TailNumber.objects.create(
            user=self.user,
            registration='N12345',
            aircraft=self.aircraft,
            is_121=False,
            is_135=False,
            is_91=True
        )

        self.flight = Flight.objects.create(
            user=self.user,
            date=date.today(),
            aircraft_type=self.aircraft,
            registration=self.tailnumber,
            route='ATL-MEM',
            duration=1.5
        )

    def test_create_flight(self):
        count = Flight.objects.count()
        Flight.objects.create(
            user=self.user,
            date=date.today(),
            aircraft_type=self.aircraft,
            registration=self.tailnumber,
            route='ATL-BHM',
            duration=2.0
        )
        self.assertEqual(Flight.objects.count(), count + 1)

    def test_read_flight(self):
        flight = Flight.objects.get(id=self.flight.id)
        self.assertEqual(flight.route, 'ATL-MEM')

    def test_update_flight(self):
        self.flight.route = 'ATL-ORD'
        self.flight.save()
        self.flight.refresh_from_db()
        self.assertEqual(self.flight.route, 'ATL-ORD')

    def test_delete_flight(self):
        flight_id = self.flight.id
        self.flight.delete()
        self.assertFalse(Flight.objects.filter(id=flight_id).exists())
