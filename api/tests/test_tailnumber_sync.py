import uuid
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase
from api.models import MobileSyncReceipt
from flights.models import Aircraft, TailNumber


@override_settings(SECURE_SSL_REDIRECT=False)
class TailnumberSyncTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tail-sync-owner')
        self.other = get_user_model().objects.create_user(username='tail-sync-other')
        Aircraft.objects.create(user=self.user, aircraft_type='C172')
        Aircraft.objects.create(user=self.other, aircraft_type='A320')
        self.client.force_authenticate(self.user)
        self.payload = {'operation_id': str(uuid.uuid4()), 'action': 'create', 'data': {
            'registration': 'n987zx', 'aircraft': 'C172', 'is_91': True, 'is_135': False, 'is_121': False,
            'user': self.other.pk}}

    def send(self, payload=None):
        return self.client.post('/api/mobile/tailnumber-sync/', payload or self.payload, format='json')

    def test_replayed_operation_returns_same_record_and_durable_receipt(self):
        first = self.send()
        self.assertEqual(first.status_code, 200, first.data)
        second = self.send()
        self.assertEqual(second.data, first.data)
        self.assertEqual(TailNumber.objects.count(), 1)
        self.assertEqual(MobileSyncReceipt.objects.count(), 1)
        record = first.data['record']
        self.assertEqual(record['registration'], 'N987ZX')
        self.assertEqual(record['user'], self.user.pk)
        self.assertEqual(len(record['revision']), 64)

    def test_same_operation_id_cannot_be_reused_for_another_payload(self):
        self.send()
        self.payload['data']['registration'] = 'N111ZX'
        self.assertEqual(self.send().status_code, 409)
        self.assertEqual(TailNumber.objects.count(), 1)

    def test_duplicate_registration_with_another_operation_is_rejected(self):
        self.send()
        self.payload['operation_id'] = str(uuid.uuid4())
        self.assertEqual(self.send().status_code, 400)
        self.assertEqual(TailNumber.objects.count(), 1)

    def test_other_users_aircraft_is_rejected_without_a_receipt(self):
        self.payload['data']['aircraft'] = 'A320'
        self.assertEqual(self.send().status_code, 400)
        self.assertFalse(TailNumber.objects.exists())
        self.assertFalse(MobileSyncReceipt.objects.exists())

    def test_requires_authentication_and_does_not_offer_deletion(self):
        self.client.force_authenticate(None)
        self.assertIn(self.send().status_code, [401, 403])
        self.client.force_authenticate(self.user)
        self.payload['action'] = 'delete'
        self.assertEqual(self.send().status_code, 400)

    def test_invalid_rules_and_registration_are_rejected(self):
        self.payload['data']['is_135'] = True
        self.assertEqual(self.send().status_code, 400)
        self.payload['data']['is_135'] = False
        self.payload['data']['registration'] = 'X' * 9
        self.assertEqual(self.send().status_code, 400)
        self.assertFalse(TailNumber.objects.exists())

    def test_flight_can_use_tailnumber_after_acknowledged_creation(self):
        self.send()
        response = self.client.post('/api/mobile/flight-sync/', {
            'operation_id': str(uuid.uuid4()), 'action': 'create', 'data': {
                'date': '11/05/2026', 'route': 'KJFK', 'duration': '1.0',
                'aircraft_type': 'C172', 'registration': 'N987ZX', 'approaches': [],
            }}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['flight']['registration'], 'N987ZX')

    def test_session_advertises_offline_tailnumber_support(self):
        self.assertTrue(self.client.get('/api/mobile/session/').data['tailnumber_sync'])
