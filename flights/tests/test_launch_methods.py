from datetime import date
from types import SimpleNamespace
import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from api.revisions import flight_revision
from flights.forms import FlightForm
from flights.launch_methods import launch_choices, validate_launch_method
from flights.models import Aircraft, Flight, TailNumber, MapData


class LaunchMethodTests(TestCase):
    def setUp(self):
        MapData.objects.create(icao='KSEA', iata='SEA', name='Seattle')
        MapData.objects.create(icao='KPDX', iata='PDX', name='Portland')
        self.user = get_user_model().objects.create_user(username='launch')
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='GLIDER', aircraft_category='GL', small=True)
        self.tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N1234', is_91=True)
        self.data = {'date': date.today(), 'aircraft_type': self.aircraft.pk, 'registration': self.tail.pk,
                     'route': 'SEA-PDX', 'duration': '1.2', 'pilot_in_command': True}

    def test_form_requires_method_on_create_and_every_update(self):
        for instance in (None, Flight.objects.create(user=self.user, aircraft_type=self.aircraft,
                registration=self.tail, date=date.today(), route='SEA-PDX', duration='1.2', pilot_in_command=True)):
            form = FlightForm(user=self.user, instance=instance, data=self.data)
            self.assertFalse(form.is_valid())
            self.assertEqual(form.errors['launch_method'], ['Choose a launch method.'])
            for method in ('AEROTOW', 'GROUND'):
                form = FlightForm(user=self.user, instance=instance, data={**self.data, 'launch_method': method})
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.save(commit=False).launch_method, method)

    def test_self_launch_is_only_offered_and_accepted_for_capable_aircraft(self):
        self.assertNotIn('SELF', dict(launch_choices(self.aircraft)))
        form = FlightForm(user=self.user, data={**self.data, 'launch_method': 'SELF'})
        self.assertFalse(form.is_valid())
        self.assertIn('launch_method', form.errors)
        self.assertIn('launch_method', validate_launch_method({'aircraft_type': self.aircraft, 'launch_method': 'SELF'}))
        self.aircraft.self_launch_capable = True
        self.aircraft.save()
        form = FlightForm(user=self.user, data={**self.data, 'launch_method': 'SELF'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIn('SELF', dict(form.fields['launch_method'].choices))

    def test_other_aircraft_and_simulator_do_not_require_launch_method(self):
        for aircraft, sim in ((SimpleNamespace(aircraft_category='A'), False), (self.aircraft, True)):
            self.assertEqual(validate_launch_method({'aircraft_type': aircraft, 'simulator': sim}), {})
            self.assertIn('launch_method', validate_launch_method({'aircraft_type': aircraft, 'simulator': sim, 'launch_method': 'GROUND'}))

    def test_form_metadata_is_owner_scoped(self):
        other = get_user_model().objects.create_user(username='other-launch')
        foreign = Aircraft.objects.create(user=other, aircraft_type='PRIVATE', aircraft_category='GL', self_launch_capable=True)
        form = FlightForm(user=self.user, data=self.data)
        self.assertNotIn(str(foreign.pk), form.launch_aircraft_metadata)
        self.assertEqual(form.launch_aircraft_metadata[str(self.aircraft.pk)]['category'], 'GL')

    def test_database_rejects_unknown_method_and_revision_tracks_changes(self):
        flight = Flight.objects.create(user=self.user, aircraft_type=self.aircraft, registration=self.tail,
            date=date.today(), route='SEA-PDX', duration='1.2', launch_method='AEROTOW')
        before = flight_revision(flight)
        flight.launch_method = 'GROUND'
        flight.save()
        self.assertNotEqual(flight_revision(flight), before)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Flight.objects.filter(pk=flight.pk).update(launch_method='OTHER')


@override_settings(SECURE_SSL_REDIRECT=False)
class LaunchSyncTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='launch-api')
        self.client.force_authenticate(self.user)
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='GLIDER', aircraft_category='GL', small=True)
        TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N1234', is_91=True)
        self.data = {'date': '11/24/2026', 'aircraft_type': 'GLIDER', 'registration': 'N1234',
                     'route': 'SEA-PDX', 'duration': '1.2', 'pilot_in_command': True, 'approaches': []}

    def send(self, **kwargs):
        return self.client.post('/api/mobile/flight-sync/', kwargs, format='json')

    def test_sync_requires_method_then_retries_and_updates_existing_flight_once(self):
        for method in ('', 'SELF', 'OTHER'):
            response = self.send(operation_id=str(uuid.uuid4()), action='create', data={**self.data, 'launch_method': method})
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn('launch_method', response.data)
        request = {'operation_id': str(uuid.uuid4()), 'action': 'create', 'data': {**self.data, 'launch_method': 'AEROTOW'}}
        first = self.send(**request)
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(self.send(**request).data, first.data)
        flight = first.data['flight']
        self.assertEqual(flight['launch_method'], 'AEROTOW')
        changed = self.send(operation_id=str(uuid.uuid4()), action='update', flight_id=flight['id'],
            base_revision=flight['revision'], data={**self.data, 'launch_method': 'GROUND'})
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertEqual(Flight.objects.count(), 1)
        self.assertEqual(Flight.objects.get().launch_method, 'GROUND')
        # Updates cannot bypass the requirement for a blank glider.
        Flight.objects.update(launch_method='')
        stored = Flight.objects.get()
        response = self.send(operation_id=str(uuid.uuid4()), action='update', flight_id=stored.pk,
            base_revision=flight_revision(stored), data={**self.data, 'remarks': 'Edited'})
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('launch_method', response.data)
