import uuid
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase
from api.models import MobileSyncReceipt
from api.revisions import flight_revision
from flights.models import Aircraft, Flight, TailNumber


@override_settings(SECURE_SSL_REDIRECT=False)
class MobileSyncTests(APITestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='mobile-owner')
        self.other = get_user_model().objects.create_user(username='mobile-other')
        aircraft = Aircraft.objects.create(user=self.owner, aircraft_type='C172')
        TailNumber.objects.create(user=self.owner, aircraft=aircraft, registration='N1234')
        self.client.force_authenticate(self.owner)
        self.data = {'date': '11/04/2026', 'route': 'KIAH-KLAS', 'duration': '1.5',
                     'aircraft_type': 'C172', 'registration': 'N1234', 'approaches': []}

    def send(self, **values):
        return self.client.post('/api/mobile/flight-sync/', values, format='json')

    def create(self):
        operation = {'operation_id': str(uuid.uuid4()), 'action': 'create', 'data': self.data}
        response = self.send(**operation)
        self.assertEqual(response.status_code, 200, response.data)
        return operation, response.data

    def test_lost_response_retry_creates_exactly_one_flight_and_receipt(self):
        operation, first = self.create()
        second = self.send(**operation)
        self.assertEqual(second.data, first)
        self.assertEqual(Flight.objects.filter(user=self.owner).count(), 1)
        self.assertEqual(MobileSyncReceipt.objects.count(), 1)

    def test_operation_id_cannot_be_reused_for_different_data(self):
        operation, first = self.create()
        operation['data'] = {**self.data, 'remarks': 'changed'}
        self.assertEqual(self.send(**operation).status_code, 409)
        self.assertEqual(Flight.objects.count(), 1)

    def test_changed_server_record_is_not_overwritten_or_deleted(self):
        _, first = self.create()
        flight = Flight.objects.get(pk=first['flight']['id'])
        flight.remarks = 'changed on website'
        flight.save()
        for action in ('update', 'delete'):
            response = self.send(operation_id=str(uuid.uuid4()), action=action,
                                 flight_id=flight.pk, base_revision=first['flight']['revision'], data=self.data)
            self.assertEqual(response.status_code, 409)
        flight.refresh_from_db()
        self.assertEqual(flight.remarks, 'changed on website')

    def test_update_replaces_approaches_and_replays_without_duplication(self):
        _, first = self.create()
        operation = {'operation_id': str(uuid.uuid4()), 'action': 'update',
                     'flight_id': first['flight']['id'], 'base_revision': first['flight']['revision'],
                     'data': {**self.data, 'remarks': 'mobile edit', 'approaches': [{'approach_type': 'ILS', 'number': 1}]}}
        updated = self.send(**operation)
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(self.send(**operation).data, updated.data)
        self.assertEqual(len(updated.data['flight']['approaches']), 1)
        operation.update(operation_id=str(uuid.uuid4()), base_revision=updated.data['flight']['revision'])
        operation['data']['approaches'] = []
        cleared = self.send(**operation)
        self.assertEqual(cleared.status_code, 200, cleared.data)
        self.assertEqual(cleared.data['flight']['approaches'], [])

    def test_delete_retry_is_acknowledged_after_flight_is_gone(self):
        _, first = self.create()
        operation = {'operation_id': str(uuid.uuid4()), 'action': 'delete',
                     'flight_id': first['flight']['id'], 'base_revision': first['flight']['revision']}
        deleted = self.send(**operation)
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.send(**operation).data, deleted.data)
        self.assertFalse(Flight.objects.exists())

    def test_another_account_cannot_edit_or_read_receipts(self):
        operation, first = self.create()
        self.client.force_authenticate(self.other)
        response = self.send(operation_id=str(uuid.uuid4()), action='delete', flight_id=first['flight']['id'],
                             base_revision=first['flight']['revision'])
        self.assertEqual(response.status_code, 409)
        self.assertNotIn('server_flight', response.data)
        response = self.send(**operation)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('flight', response.data)

    def test_receipt_failure_rolls_back_the_flight(self):
        with patch('api.mobile_sync.MobileSyncReceipt.objects.create', side_effect=RuntimeError('disk failure')):
            with self.assertRaises(RuntimeError):
                self.send(operation_id=str(uuid.uuid4()), action='create', data=self.data)
        self.assertFalse(Flight.objects.exists())
        self.assertFalse(MobileSyncReceipt.objects.exists())

    def test_validation_does_not_write_receipt_and_requires_authentication(self):
        self.assertEqual(self.send(operation_id=str(uuid.uuid4()), action='create', data={}).status_code, 400)
        self.assertFalse(MobileSyncReceipt.objects.exists())
        self.assertEqual(self.client.get('/api/mobile/session/').data['account_id'], self.owner.pk)
        self.client.force_authenticate(None)
        self.assertIn(self.send(operation_id=str(uuid.uuid4()), action='create', data=self.data).status_code, (401, 403))


from concurrent.futures import ThreadPoolExecutor
from django.db import close_old_connections, connection
from rest_framework.test import APIClient, APITransactionTestCase
from unittest import skipUnless


@override_settings(SECURE_SSL_REDIRECT=False)
@skipUnless(connection.vendor == 'postgresql', 'Requires PostgreSQL row locks')
class MobileSyncConcurrencyTests(APITransactionTestCase):
    setUp = MobileSyncTests.setUp

    def test_concurrent_same_operation_commits_one_flight(self):
        operation = {'operation_id': str(uuid.uuid4()), 'action': 'create', 'data': self.data}
        owner_id = self.owner.pk

        def upload():
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(get_user_model().objects.get(pk=owner_id))
                response = client.post('/api/mobile/flight-sync/', operation, format='json')
                return response.status_code, response.data
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: upload(), range(2)))
        self.assertEqual([result[0] for result in results], [200, 200], results)
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(Flight.objects.filter(user=self.owner).count(), 1)
        self.assertEqual(MobileSyncReceipt.objects.count(), 1)
