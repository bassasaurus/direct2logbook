from django.test import TestCase, override_settings
from django.contrib.auth.models import User, Group
from django.urls import reverse
from flights.models import Aircraft, TailNumber, Flight, MapData, Approach, Holding
from django.db.models.signals import post_save
from datetime import date


class FlightCRUDTests(TestCase):
    def setUp(self):
        # Ensure the 'clients' group exists for the profile signal
        Group.objects.get_or_create(name='clients')

        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpass',
        )

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
            date=date(2025, 7, 28),
            aircraft_type=self.aircraft,
            registration=self.tailnumber,
            route='ATL-MEM',
            duration=1.5
        )

    def test_create_flight(self):
        count = Flight.objects.count()
        Flight.objects.create(
            user=self.user,
            date=date(2025, 7, 28),
            aircraft_type=self.aircraft,
            registration=self.tailnumber,
            route='ATL-KLAX',
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


    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_delete_view_returns_to_logbook(self):
        self.user.profile.active = True
        self.user.profile.expired = False
        self.user.profile.save()
        self.client.force_login(self.user)
        response = self.client.post(reverse('flight_delete', args=[self.flight.pk]))
        self.assertFalse(Flight.objects.filter(pk=self.flight.pk).exists())
        self.assertRedirects(response, reverse('flight_list'), fetch_redirect_response=False)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_update_view_saves_once_with_inline_records_and_totals(self):
        for code in ('ATL', 'MEM'):
            MapData.objects.create(icao='K' + code, iata=code, name=code, country='United States')
        self.user.profile.active = True
        self.user.profile.expired = False
        self.user.profile.save()
        self.client.force_login(self.user)
        saves = []

        def count_saves(sender, instance, **kwargs):
            saves.append(instance.pk)

        post_save.connect(count_saves, sender=Flight, weak=False)
        try:
            response = self.client.post(reverse('flight_update', args=[self.flight.pk]), {
                'date': '07/28/2025', 'aircraft_type': self.aircraft.pk,
                'registration': self.tailnumber.pk, 'route': 'ATL-MEM',
                'duration': '2.5', 'pilot_in_command': True,
                'approach_set-TOTAL_FORMS': '1', 'approach_set-INITIAL_FORMS': '0',
                'approach_set-0-approach_type': 'ILS', 'approach_set-0-number': '1',
                'holding_set-TOTAL_FORMS': '1', 'holding_set-INITIAL_FORMS': '0',
                'holding_set-0-hold': True,
            })
        finally:
            post_save.disconnect(count_saves, sender=Flight)
        self.assertRedirects(response, self.flight.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual(saves, [self.flight.pk])
        self.flight.refresh_from_db()
        self.assertEqual(self.flight.duration, 2.5)
        self.assertTrue(Approach.objects.filter(flight_object=self.flight, approach_type='ILS', number=1).exists())
        self.assertTrue(Holding.objects.filter(flight_object=self.flight, hold=True).exists())
        self.assertEqual(self.user.total_set.get(total='All').total_time, 2.5)
