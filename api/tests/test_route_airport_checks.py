from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase
from flights.models import Aircraft, AirportCode, Flight, MapData, TailNumber


@override_settings(SECURE_SSL_REDIRECT=False)
class MobileAirportChecksTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='airport-mobile')
        self.client.force_authenticate(self.user)
        self.us = MapData.objects.create(name='US airport', country='United States', iata='LBX', icao='KLBX')
        self.foreign = MapData.objects.create(name='Foreign airport', country='Philippines', iata='LBX', icao='RPLU')
        self.bog = MapData.objects.create(name='Bogota', country='Colombia', iata='BOG', icao='SKBO')
        self.faa = MapData.objects.create(name='FAA field', country='United States', icao='')
        AirportCode.objects.create(airport=self.faa, code='2TX1', kind='faa')
        self.a = Aircraft.objects.create(user=self.user, aircraft_type='C172')
        self.tail = TailNumber.objects.create(user=self.user, aircraft=self.a, registration='N123')

    def check(self, route):
        return self.client.get('/api/mobile/route-airport-check/', {'route': route})

    def payload(self, route, **extra):
        return {'date': '11/05/2026', 'route': route, 'duration': '1.0', 'aircraft_type': 'C172',
                'registration': 'N123', 'approaches': [], 'pilot_in_command': True, 'validate_airports': True, **extra}

    def test_checks_reuse_us_preference_international_and_faa_rules(self):
        response = self.check('lbx-BOG-2TX1-RPLU-ZZZZ')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        entries = response.data['entries']
        self.assertEqual([entry['status'] for entry in entries], ['recognized'] * 4 + ['unknown'])
        self.assertEqual(entries[0]['airport']['id'], self.us.pk)
        self.assertEqual(entries[2]['airport']['id'], self.faa.pk)
        self.assertEqual(entries[3]['airport']['id'], self.foreign.pk)

    def test_authentication_and_route_length_are_enforced(self):
        self.assertEqual(self.check('A' * 51).status_code, 400)
        self.client.force_authenticate(None)
        self.assertIn(self.check('LBX').status_code, [401, 403])

    def test_unknown_codes_are_rejected_on_opted_in_save(self):
        response = self.client.post('/api/flights/', self.payload('ZZZZ'), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('route', response.data)
        self.assertFalse(Flight.objects.filter(user=self.user).exists())

    def test_ambiguous_airport_requires_choice_and_saves_it(self):
        first = MapData.objects.create(name='First', country='Canada', iata='XYZ', icao='CXYZ')
        MapData.objects.create(name='Second', country='Mexico', iata='XYZ', icao='MXYZ')
        self.assertEqual(self.check('XYZ').data['entries'][0]['status'], 'ambiguous')
        self.assertEqual(self.client.post('/api/flights/', self.payload('XYZ'), format='json').status_code, 400)
        choices = {'route': 'XYZ', 'airports': {'0': first.pk}}
        response = self.client.post('/api/flights/', self.payload('XYZ', route_airport_choices=choices), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['route_airport_choices'], choices)
        self.assertEqual(Flight.objects.get(pk=response.data['id']).route_airport_choices, choices)

    def test_cannot_spoof_an_unrelated_airport_choice(self):
        response = self.client.post('/api/flights/', self.payload('LBX', route_airport_choices={
            'route': 'LBX', 'airports': {'0': self.bog.pk}}), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('route_airport_choices', response.data)

    def test_existing_api_clients_keep_their_route_contract(self):
        data = self.payload('ZZZZ')
        data.pop('validate_airports')
        self.assertEqual(self.client.post('/api/flights/', data, format='json').status_code, 201)
