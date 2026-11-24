import uuid
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase
from api.revisions import aircraft_revision
from flights.models import Aircraft


@override_settings(SECURE_SSL_REDIRECT=False)
class AircraftClassificationAPITests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='classification-api')
        self.client.force_authenticate(self.user)

    def send(self, data, **kwargs):
        return self.client.post('/api/mobile/aircraft-sync/',
            {'operation_id': str(uuid.uuid4()), 'action': 'create', 'data': data, **kwargs}, format='json')

    def payload(self, category, klass=''):
        return {'aircraft_type': 'TEST', 'aircraft_category': category, 'aircraft_class': klass,
                'piston': True, 'small': True}

    def test_create_each_new_category_and_retry_without_duplicate(self):
        for category, klass in (('GL', ''), ('PL', ''), ('LTA', 'BALLOON'), ('LTA', 'AIRSHIP')):
            with self.subTest(category=category, klass=klass):
                data = {**self.payload(category, klass), 'aircraft_type': f'T{Aircraft.objects.count()}'}
                request = {'operation_id': str(uuid.uuid4()), 'action': 'create', 'data': data}
                response = self.client.post('/api/mobile/aircraft-sync/', request, format='json')
                self.assertEqual(response.status_code, 200, response.data)
                replay = self.client.post('/api/mobile/aircraft-sync/', request, format='json')
                self.assertEqual(response.data, replay.data)
                self.assertEqual(Aircraft.objects.get(pk=response.data['record']['id']).aircraft_class, klass)
        self.assertEqual(Aircraft.objects.filter(user=self.user).count(), 4)

    def test_required_mismatched_and_inapplicable_classes_get_field_errors(self):
        for category, klass in (('A', ''), ('R', ''), ('LTA', ''), ('LTA', 'SEL'), ('GL', 'SEL'), ('PL', 'HELO')):
            response = self.send(self.payload(category, klass))
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn('aircraft_class', response.data)
        self.assertFalse(Aircraft.objects.filter(user=self.user).exists())

    def test_older_queued_payload_and_revision_still_update_without_reclassification(self):
        aircraft = Aircraft.objects.create(user=self.user, aircraft_type='TEST', aircraft_category='A',
                                           aircraft_class='SEL', piston=True, small=True)
        revision = aircraft_revision(aircraft)
        response = self.send({**self.payload('A', 'SEL'), 'simple': True}, action='update',
                             record_id=aircraft.pk, base_revision=revision)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['record']['aircraft_category'], 'A')
        self.assertEqual(response.data['record']['aircraft_class'], 'SEL')

    def test_unchanged_legacy_blank_class_is_not_rejected(self):
        aircraft = Aircraft.objects.create(user=self.user, aircraft_type='TEST', aircraft_category='A',
                                           piston=True, small=True)
        response = self.send({**self.payload('A'), 'simple': True}, action='update',
                             record_id=aircraft.pk, base_revision=aircraft_revision(aircraft))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['record']['aircraft_class'], '')
