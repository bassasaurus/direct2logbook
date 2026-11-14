import base64
from io import BytesIO
from PIL import Image
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase
from api.mobile_signature import signature_revision
from signature.models import Signature


@override_settings(SECURE_SSL_REDIRECT=False)
class MobileSignatureTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='signature-owner')
        self.other = get_user_model().objects.create_user(username='signature-other')
        self.url = '/api/mobile/signature/'
        self.payload = {'revision': signature_revision(None), 'strokes': [[[.1, .3], [.4, .7], [.8, .2]]]}

    def test_authentication_required(self):
        self.assertIn(self.client.put(self.url, self.payload, format='json').status_code, (401, 403))
        self.assertFalse(Signature.objects.exists())

    def test_creates_png_visible_in_profile_and_retries_safely(self):
        self.client.force_authenticate(self.user)
        response = self.client.put(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        raw = response.data['signature']
        image = Image.open(BytesIO(base64.b64decode(raw.split(',')[1])))
        self.assertEqual(image.size, (900, 300))
        self.assertIsNotNone(image.getbbox())
        self.assertEqual(self.client.get('/api/mobile/profile/').data['signature'], raw)
        self.assertEqual(self.client.put(self.url, self.payload, format='json').status_code, 200)
        self.assertEqual(Signature.objects.filter(user=self.user).count(), 1)
        self.assertFalse(Signature.objects.filter(user=self.other).exists())

    def test_replaces_existing_and_rejects_stale_revision(self):
        self.client.force_authenticate(self.user)
        first = self.client.put(self.url, self.payload, format='json').data
        changed = {'revision': first['signature_revision'], 'strokes': [[[.2, .2], [.5, .8]]]}
        second = self.client.put(self.url, changed, format='json')
        self.assertEqual(second.status_code, 200)
        self.assertNotEqual(first['signature'], second.data['signature'])
        self.assertEqual(self.client.put(self.url, self.payload, format='json').status_code, 409)
        self.assertEqual(Signature.objects.get(user=self.user).signature, second.data['signature'])

    def test_invalid_input_preserves_signature(self):
        self.client.force_authenticate(self.user)
        self.client.put(self.url, self.payload, format='json')
        before = Signature.objects.get(user=self.user).signature
        for strokes in ([], [[[.5, .5]]], [[[0, 0], [2, 1]]], [[[0, 0, 0]]], [[[0, 0]]] * 201):
            response = self.client.put(self.url, {**self.payload, 'strokes': strokes}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(self.client.put(self.url, {**self.payload, 'user': self.other.pk}, format='json').status_code, 400)
        self.assertEqual(Signature.objects.get(user=self.user).signature, before)
