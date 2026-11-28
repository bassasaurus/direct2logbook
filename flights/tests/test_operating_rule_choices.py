import hashlib
import json
import uuid
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from api.serializers import TailNumberSerializer
from flights.admin import TailnumberAdminForm
from flights.forms import ImportedForm, TailNumberForm
from flights.models import Aircraft, TailNumber
from flights.operating_rules import OPERATING_RULE_CHOICES, OPERATING_RULE_FIELDS


@override_settings(SECURE_SSL_REDIRECT=False)
class OperatingRuleChoiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('additional-rules')
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='C172')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_forms_and_api_accept_each_rule_and_store_exactly_one(self):
        self.assertEqual([field for field, _ in OPERATING_RULE_CHOICES],
                         ['is_91', 'is_121', 'is_125', 'is_135', 'is_137'])
        for field in OPERATING_RULE_FIELDS:
            with self.subTest(field=field):
                form = TailNumberForm({'aircraft': self.aircraft.pk, 'registration': f'N{field[3:]}',
                                       'operating_rules': field}, user=self.user)
                self.assertTrue(form.is_valid(), form.errors)
                tail = form.save(commit=False)
                tail.user = self.user
                tail.save()
                self.assertEqual([key for key in OPERATING_RULE_FIELDS if getattr(tail, key)], [field])
                data = {key: key == field for key in OPERATING_RULE_FIELDS}
                serializer = TailNumberSerializer(tail, data=data, partial=True,
                    context={'request': SimpleNamespace(user=self.user)})
                self.assertTrue(serializer.is_valid(), serializer.errors)
                balance = ImportedForm({'aircraft_type': self.aircraft.pk, 'operating_rules': field}, user=self.user)
                self.assertTrue(balance.is_valid(), balance.errors)

    def test_missing_multiple_and_legacy_invalid_selections_cannot_be_saved(self):
        for rules in ({}, {'is_91': True, 'is_125': True}, {'is_125': True, 'is_137': True}):
            serializer = TailNumberSerializer(data={'registration': 'N999', 'aircraft': self.aircraft.pk, **rules},
                context={'request': SimpleNamespace(user=self.user)})
            self.assertFalse(serializer.is_valid())
            self.assertIn('operating_rules', serializer.errors)
        legacy = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N888', is_91=True, is_135=True)
        form = TailNumberForm({'aircraft': self.aircraft.pk, 'registration': 'N888'}, instance=legacy, user=self.user)
        self.assertFalse(form.is_valid())
        legacy.refresh_from_db()
        self.assertTrue(legacy.is_91 and legacy.is_135)
        admin_form = TailnumberAdminForm({'user': self.user.pk, 'aircraft': self.aircraft.pk,
            'registration': 'N777', 'is_125': True, 'is_137': True})
        self.assertFalse(admin_form.is_valid())

    def test_new_rules_survive_offline_sync_replay(self):
        for rule in ('125', '137'):
            payload = {'action': 'create', 'operation_id': str(uuid.uuid4()), 'data': {
                'registration': f'N{rule}X', 'aircraft': 'C172', f'is_{rule}': True}}
            response = self.client.post('/api/mobile/tailnumber-sync/', payload, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            replay = self.client.post('/api/mobile/tailnumber-sync/', payload, format='json')
            self.assertEqual(response.data, replay.data)
            self.assertTrue(response.data['record'][f'is_{rule}'])
            self.assertEqual(TailNumber.objects.filter(registration=f'N{rule}X').count(), 1)

    def test_unused_new_options_preserve_existing_mobile_revision(self):
        tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N123', is_91=True)
        before = {field.attname: getattr(tail, field.attname) for field in tail._meta.concrete_fields
                  if field.name not in ('is_125', 'is_137')}
        expected = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
        self.assertEqual(TailNumberSerializer(tail).data['revision'], expected)
        tail.is_125 = True
        self.assertNotEqual(TailNumberSerializer(tail).data['revision'], expected)
