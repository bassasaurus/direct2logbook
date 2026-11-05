import uuid
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase
from api.revisions import aircraft_revision
from api.models import MobileSyncReceipt
from flights.models import Aircraft, Flight, Imported, TailNumber


@override_settings(SECURE_SSL_REDIRECT=False)
class AircraftSyncTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='aircraft-sync')
        self.other = get_user_model().objects.create_user(username='other-aircraft-sync')
        self.client.force_authenticate(self.user)
        self.payload = {'aircraft_type': 'C172', 'aircraft_category': 'A', 'aircraft_class': 'SEL', 'piston': True}

    def send(self, **values):
        return self.client.post('/api/mobile/aircraft-sync/', values, format='json')

    def create(self):
        values = {'operation_id': str(uuid.uuid4()), 'action': 'create', 'data': self.payload}
        response = self.send(**values)
        self.assertEqual(response.status_code, 200, response.data)
        return values, response.data['record']

    def test_create_retry_does_not_duplicate_aircraft(self):
        values, record = self.create()
        replay = self.send(**values)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.data['record'], record)
        self.assertEqual(Aircraft.objects.count(), 1)
        self.assertEqual(MobileSyncReceipt.objects.count(), 1)

    def test_update_and_delete_replay_without_repeating_writes(self):
        _, record = self.create()
        values = {'operation_id': str(uuid.uuid4()), 'action': 'update', 'record_id': record['id'],
                  'base_revision': record['revision'], 'data': {**self.payload, 'high_performance': True}}
        updated = self.send(**values)
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertTrue(updated.data['record']['high_performance'])
        self.assertEqual(self.send(**values).data, updated.data)
        deleted = {'operation_id': str(uuid.uuid4()), 'action': 'delete', 'record_id': record['id'],
                   'base_revision': updated.data['record']['revision']}
        response = self.send(**deleted)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.send(**deleted).data, response.data)
        self.assertFalse(Aircraft.objects.exists())

    def test_stale_update_and_foreign_delete_are_rejected(self):
        _, record = self.create()
        Aircraft.objects.filter(pk=record['id']).update(tailwheel=True)
        response = self.send(operation_id=str(uuid.uuid4()), action='update', record_id=record['id'],
                             base_revision=record['revision'], data=self.payload)
        self.assertEqual(response.status_code, 409)
        self.client.force_authenticate(self.other)
        response = self.send(operation_id=str(uuid.uuid4()), action='delete', record_id=record['id'], base_revision=record['revision'])
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Aircraft.objects.filter(pk=record['id']).exists())

    def test_used_aircraft_cannot_cascade_delete_its_tailnumbers_or_flights(self):
        _, record = self.create()
        aircraft = Aircraft.objects.get(pk=record['id'])
        tail = TailNumber.objects.create(user=self.user, aircraft=aircraft, registration='N1234')
        flight = Flight.objects.create(user=self.user, aircraft_type=aircraft, registration=tail,
                                      date='2026-11-04', route='KIAH-KLAS', duration='1.0')
        response = self.send(operation_id=str(uuid.uuid4()), action='delete', record_id=record['id'], base_revision=record['revision'])
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Flight.objects.filter(pk=flight.pk).exists())
        self.assertTrue(TailNumber.objects.filter(pk=tail.pk).exists())

    def test_imported_totals_also_prevent_deletion(self):
        _, record = self.create()
        Imported.objects.create(user=self.user, aircraft_type_id=record['id'])
        response = self.send(operation_id=str(uuid.uuid4()), action='delete', record_id=record['id'], base_revision=record['revision'])
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Aircraft.objects.filter(pk=record['id']).exists())

    def test_rename_and_reused_operation_payload_are_rejected(self):
        values, record = self.create()
        values['data'] = {**self.payload, 'aircraft_type': 'C182'}
        self.assertEqual(self.send(**values).status_code, 409)
        response = self.send(operation_id=str(uuid.uuid4()), action='update', record_id=record['id'],
                             base_revision=record['revision'], data=values['data'])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Aircraft.objects.get(pk=record['id']).aircraft_type, 'C172')

    def test_validation_and_owner_spoofing(self):
        self.assertEqual(self.send(operation_id=str(uuid.uuid4()), action='create', data={}).status_code, 400)
        response = self.send(operation_id=str(uuid.uuid4()), action='create', data={**self.payload, 'user': self.other.pk})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['record']['user'], self.user.pk)
