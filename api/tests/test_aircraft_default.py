import uuid
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import override_settings
from rest_framework.test import APITestCase
from api.models import MobileSyncReceipt
from api.revisions import aircraft_revision
from flights.models import Aircraft


@override_settings(SECURE_SSL_REDIRECT=False)
class DefaultAircraftSyncTests(APITestCase):
    path = '/api/mobile/default-aircraft/'

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='default-owner')
        self.other = get_user_model().objects.create_user(username='default-other')
        self.first = Aircraft.objects.create(user=self.user, aircraft_type='C172')
        self.second = Aircraft.objects.create(user=self.user, aircraft_type='A320')
        self.foreign = Aircraft.objects.create(user=self.other, aircraft_type='PA28', is_default=True)
        self.client.force_authenticate(self.user)

    def operation(self, code, revision=None):
        return {'operation_id': str(uuid.uuid4()), 'action': 'update',
                'base_revision': revision or self.client.get(self.path).data['revision'],
                'data': {'aircraft_type': code}}

    def test_selection_replay_switch_and_clear_are_idempotent(self):
        revision = aircraft_revision(self.first)
        request = self.operation('C172')
        first = self.client.post(self.path, request, format='json')
        replay = self.client.post(self.path, request, format='json')
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data, replay.data)
        self.assertEqual(MobileSyncReceipt.objects.filter(user=self.user).count(), 1)
        self.assertEqual(self.client.post(self.path, self.operation('A320'), format='json').status_code, 200)
        self.first.refresh_from_db(); self.second.refresh_from_db(); self.foreign.refresh_from_db()
        self.assertFalse(self.first.is_default)
        self.assertTrue(self.second.is_default)
        self.assertTrue(self.foreign.is_default)
        self.assertEqual(aircraft_revision(self.first), revision)  # Independent preference revision.
        self.assertEqual(self.client.post(self.path, self.operation(''), format='json').status_code, 200)
        self.assertFalse(Aircraft.objects.filter(user=self.user, is_default=True).exists())

    def test_stale_revision_conflicts_without_overwriting_server_default(self):
        stale = self.operation('A320')
        self.client.post(self.path, self.operation('C172'), format='json')
        response = self.client.post(self.path, stale, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get(self.path).data['aircraft_type'], 'C172')

    def test_requires_auth_and_rejects_another_owners_aircraft(self):
        response = self.client.post(self.path, self.operation('PA28'), format='json')
        self.assertEqual(response.status_code, 400)
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(self.path).status_code, (401, 403))

    def test_constraint_blocks_two_defaults_for_one_owner(self):
        Aircraft.objects.filter(pk=self.first.pk).update(is_default=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Aircraft.objects.filter(pk=self.second.pk).update(is_default=True)

    def test_aircraft_api_exposes_but_does_not_allow_spoofed_default_changes(self):
        response = self.client.patch('/api/aircraft/' + str(self.first.pk) + '/', {'is_default': True}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn('is_default', response.data)
        self.first.refresh_from_db()
        self.assertFalse(self.first.is_default)

    def test_operation_id_cannot_be_reused_with_different_selection(self):
        request = self.operation('C172')
        self.client.post(self.path, request, format='json')
        request['data']['aircraft_type'] = 'A320'
        self.assertEqual(self.client.post(self.path, request, format='json').status_code, 409)

    def test_default_updates_do_not_stale_queued_aircraft_edits(self):
        base = aircraft_revision(self.first)
        self.client.post(self.path, self.operation('C172'), format='json')
        response = self.client.post('/api/mobile/aircraft-sync/', {
            'operation_id': str(uuid.uuid4()), 'action': 'update', 'record_id': self.first.pk,
            'base_revision': base, 'data': {'aircraft_type': 'C172', 'piston': True},
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.first.refresh_from_db()
        self.assertTrue(self.first.is_default)
        self.assertTrue(self.first.piston)

    def test_empty_baseline_matches_offline_initial_selection(self):
        self.assertEqual(self.client.get(self.path).data['revision'],
                         'dfa61a1cc9252b9445b3f8bf6e6f4bf89acbfafba3266a146d8cf1f67fe62d3b')
