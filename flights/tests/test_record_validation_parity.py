from datetime import date

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from flights.forms import AircraftForm, FlightForm, TailNumberForm
from flights.models import Aircraft, Flight, MapData, TailNumber


@override_settings(SECURE_SSL_REDIRECT=False)
class RecordValidationParityTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='validation')
        cls.aircraft = Aircraft.objects.create(
            user=cls.user, aircraft_type='C172', piston=True, turbine=True,
        )
        cls.tailnumber = TailNumber.objects.create(
            user=cls.user, aircraft=cls.aircraft, registration='LEGACY123',
        )
        cls.flight = Flight.objects.create(
            user=cls.user, aircraft_type=cls.aircraft, registration=cls.tailnumber,
            date=date(2026, 1, 1), duration='1.0', route='KJFK',
            simulator=True, cross_country=True,
        )
        MapData.objects.create(icao='KJFK', iata='JFK', name='John F Kennedy', country='United States')

    def setUp(self):
        self.client.force_authenticate(self.user)
        self.flight_data = {'date': '01/01/2026', 'duration': '1.0', 'route': 'KJFK'}
        self.web_flight_data = {
            **self.flight_data, 'aircraft_type': self.aircraft.pk, 'registration': self.tailnumber.pk,
        }
        self.api_flight_data = {
            **self.flight_data, 'aircraft_type': 'C172', 'registration': 'LEGACY123',
        }

    def test_new_flight_rejects_invalid_combinations_in_form_and_api(self):
        for values, field in (
            ({}, 'pilot_in_command'),
            ({'solo': True}, 'landings_day'),
            ({'pilot_in_command': True, 'simulator': True, 'cross_country': True}, 'cross_country'),
        ):
            with self.subTest(field=field):
                form = FlightForm(data={**self.web_flight_data, **values}, user=self.user)
                self.assertIn(field, form.errors)
                response = self.client.post('/api/flights/', {**self.api_flight_data, **values}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(field, response.data)

    def test_night_time_and_night_landings_do_not_block_each_other(self):
        for values in ({'landings_night': 1}, {'night': 0.5}):
            with self.subTest(values=values):
                form = FlightForm(
                    data={**self.web_flight_data, 'pilot_in_command': True, **values}, user=self.user,
                )
                self.assertTrue(form.is_valid(), form.errors)
                response = self.client.post(
                    '/api/flights/', {**self.api_flight_data, 'pilot_in_command': True, **values}, format='json',
                )
                self.assertEqual(response.status_code, 201, response.data)

    def test_legacy_flight_allows_unrelated_edits_but_checks_landing_changes(self):
        form = FlightForm(
            data={**self.web_flight_data, 'simulator': True, 'cross_country': True, 'remarks': 'Edited'},
            instance=self.flight, user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        url = f'/api/flights/{self.flight.pk}/'
        response = self.client.patch(url, {'solo': True, 'landings_day': 1}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        response = self.client.patch(url, {'landings_day': ''}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('landings_day', response.data)
        self.flight.refresh_from_db()
        self.assertEqual(self.flight.landings_day, 1)
        self.assertTrue(self.flight.cross_country)

    def test_new_aircraft_requires_classification_engine_and_weight(self):
        response = self.client.post('/api/aircraft/', {'aircraft_type': 'H125'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(set(response.data), {'aircraft_category', 'aircraft_class', 'engine', 'weight_category'})
        form = AircraftForm(data={
            'aircraft_type': 'H125', 'aircraft_category': 'R', 'aircraft_class': 'SEL',
            'engine': 'turbine', 'weight_category': 'small',
        })
        self.assertIn('aircraft_class', form.errors)

    def test_aircraft_form_preserves_untouched_legacy_flags(self):
        form = AircraftForm(data={'aircraft_type': 'C172', 'high_performance': True}, instance=self.aircraft)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.aircraft.refresh_from_db()
        self.assertTrue(self.aircraft.high_performance)
        self.assertTrue(self.aircraft.piston)
        self.assertTrue(self.aircraft.turbine)
        url = f'/api/aircraft/{self.aircraft.pk}/'
        response = self.client.patch(url, {'aircraft_category': 'A'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('aircraft_class', response.data)
        response = self.client.patch(url, {'piston': False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)

    def test_tailnumber_enforces_new_values_and_preserves_legacy_values(self):
        response = self.client.post('/api/tailnumbers/', {'aircraft': 'C172', 'registration': 'N1'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(set(response.data), {'registration', 'operating_rules'})
        replacement = Aircraft.objects.create(user=self.user, aircraft_type='C182')
        form = TailNumberForm(
            data={'registration': 'LEGACY123', 'aircraft': replacement.pk},
            instance=self.tailnumber, user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        url = f'/api/tailnumbers/{self.tailnumber.pk}/'
        response = self.client.patch(url, {'registration': 'X' * 10}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('registration', response.data)
        response = self.client.patch(url, {'is_91': True}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        response = self.client.patch(url, {'is_91': False}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('operating_rules', response.data)
