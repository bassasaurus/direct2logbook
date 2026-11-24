import hashlib
import json
import uuid
from datetime import date

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import override_settings
from rest_framework.test import APITestCase

from api.revisions import aircraft_revision
from flights.forms import AircraftForm, FlightForm
from flights.models import Aircraft, Flight, TailNumber


@override_settings(SECURE_SSL_REDIRECT=False)
class AircraftFlightDefaultsTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='flight-defaults')
        self.other = get_user_model().objects.create_user(username='other-flight-defaults')
        self.client.force_authenticate(self.user)
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='C172',
            aircraft_category='A', aircraft_class='SEL', piston=True, small=True, is_default=True)
        self.url = f'/api/aircraft/{self.aircraft.pk}/flight-defaults/'

    def change(self, role='PIC', xc=True, revision=None, url=None):
        return self.client.post(url or self.url, {'base_revision': revision or aircraft_revision(self.aircraft),
            'default_crew_role': role, 'default_cross_country': xc}, format='json')

    def test_detail_preferences_save_return_revision_and_do_not_change_flights(self):
        tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N123')
        flight = Flight.objects.bulk_create([Flight(user=self.user, aircraft_type=self.aircraft,
            registration=tail, date=date(2026, 11, 24), route='IAH-DAL', duration=1, pilot_in_command=False,
            second_in_command=True, cross_country=False)])[0]
        original = list(Flight.objects.filter(pk=flight.pk).values())
        old_revision = aircraft_revision(self.aircraft)
        response = self.change()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['record']['default_crew_role'], 'PIC')
        self.assertTrue(response.data['record']['default_cross_country'])
        self.assertNotEqual(response.data['record']['revision'], old_revision)
        self.assertEqual(list(Flight.objects.filter(pk=flight.pk).values()), original)
        replay = self.change(revision=old_revision)
        self.assertEqual(replay.status_code, 200)

    def test_stale_conflicting_choice_is_rejected_and_foreign_aircraft_is_hidden(self):
        revision = aircraft_revision(self.aircraft)
        self.assertEqual(self.change().status_code, 200)
        response = self.change('SIC', revision=revision)
        self.assertEqual(response.status_code, 409)
        self.aircraft.refresh_from_db()
        self.assertEqual(self.aircraft.default_crew_role, 'PIC')
        foreign = Aircraft.objects.create(user=self.other, aircraft_type='OTHER')
        self.assertEqual(self.change(url=f'/api/aircraft/{foreign.pk}/flight-defaults/').status_code, 404)

    def test_invalid_role_is_rejected_by_api_and_database(self):
        self.assertEqual(self.change('XYZ').status_code, 400)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Aircraft.objects.filter(pk=self.aircraft.pk).update(default_crew_role='XYZ')

    def test_web_session_requires_csrf(self):
        from rest_framework.test import APIClient
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(self.url, {'base_revision': aircraft_revision(self.aircraft),
            'default_crew_role': 'SIC', 'default_cross_country': True}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_neutral_defaults_preserve_preupgrade_revision(self):
        values = {f.attname: str(getattr(self.aircraft, f.attname)) for f in self.aircraft._meta.concrete_fields
            if f.attname not in ('is_default', 'electric', 'self_launch_capable', 'default_crew_role', 'default_cross_country')}
        values.update(medium='False', light_sport='False')
        before = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
        self.assertEqual(aircraft_revision(self.aircraft), before)

    def test_only_unbound_new_flights_receive_defaults(self):
        Aircraft.objects.filter(pk=self.aircraft.pk).update(default_crew_role='SIC', default_cross_country=True)
        fresh = FlightForm(user=self.user)
        self.assertEqual(fresh.initial['aircraft_type'], self.aircraft.pk)
        self.assertFalse(fresh['pilot_in_command'].value())
        self.assertTrue(fresh['second_in_command'].value())
        self.assertTrue(fresh['cross_country'].value())
        bound = FlightForm(data={'aircraft_type': self.aircraft.pk, 'pilot_in_command': True}, user=self.user)
        self.assertTrue(bound['pilot_in_command'].value())
        self.assertFalse(bound['second_in_command'].value())
        self.assertFalse(bound['cross_country'].value())
        tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N123')
        flight = Flight.objects.bulk_create([Flight(user=self.user, aircraft_type=self.aircraft, registration=tail,
            date=date(2026, 11, 24), route='IAH-DAL', duration=1, pilot_in_command=True, cross_country=False)])[0]
        existing = FlightForm(instance=flight, user=self.user)
        self.assertTrue(existing['pilot_in_command'].value())
        self.assertFalse(existing['second_in_command'].value())
        self.assertFalse(existing['cross_country'].value())

    def test_aircraft_update_form_does_not_reset_preferences(self):
        self.aircraft.default_crew_role, self.aircraft.default_cross_country = 'SIC', True
        self.aircraft.save()
        form = AircraftForm(data={'aircraft_type': 'C172', 'aircraft_category': 'A', 'aircraft_class': 'SEL',
            'engine': 'piston', 'weight_category': 'small'}, instance=self.aircraft, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(saved.default_crew_role, 'SIC')
        self.assertTrue(saved.default_cross_country)

    def test_mobile_queue_retry_and_old_payload_preserve_defaults(self):
        payload = {'aircraft_type': 'B737', 'aircraft_category': 'A', 'aircraft_class': 'MEL',
            'turbine': True, 'large': True, 'default_crew_role': 'SIC', 'default_cross_country': True}
        operation = {'operation_id': str(uuid.uuid4()), 'action': 'create', 'data': payload}
        url = '/api/mobile/aircraft-sync/'
        response = self.client.post(url, operation, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.client.post(url, operation, format='json').data, response.data)
        record = response.data['record']
        legacy = {key: value for key, value in payload.items() if not key.startswith('default_')}
        updated = self.client.post(url, {'operation_id': str(uuid.uuid4()), 'action': 'update',
            'record_id': record['id'], 'base_revision': record['revision'], 'data': legacy}, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data['record']['default_crew_role'], 'SIC')
        self.assertTrue(updated.data['record']['default_cross_country'])
        self.assertEqual(Aircraft.objects.filter(user=self.user, aircraft_type='B737').count(), 1)
