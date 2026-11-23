import base64
import json
from io import BytesIO, StringIO
from unittest.mock import patch
from cryptography.fernet import Fernet, InvalidToken
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from PIL import Image
from .models import Signature
from .encryption import decrypt_payload, SignatureDecryptionError
from .forms import SignatureForm
from .rendering import render_signature
from .strokes import validate_strokes

KEY = Fernet.generate_key().decode()
STROKES = [[[.1, .3], [.4, .7], [.8, .2]]]


@override_settings(SIGNATURE_ENCRYPTION_KEYS=[KEY], SIGNATURE_ENCRYPTION_KEY_FILE='')
class EncryptedSignatureTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('encrypted-signature')

    def signature(self):
        sig = Signature(user=self.user)
        sig.set_strokes(STROKES)
        sig.save()
        return sig

    def test_database_contains_only_ciphertext_and_rendering_survives_reload(self):
        sig = self.signature()
        with connection.cursor() as cursor:
            cursor.execute('SELECT signature, encrypted_data FROM signature_signature WHERE id = %s', [sig.pk])
            legacy, encrypted = cursor.fetchone()
        self.assertIsNone(legacy)
        self.assertTrue(encrypted.startswith('gAAAA'))
        self.assertNotIn('strokes', encrypted)
        self.assertEqual(decrypt_payload(encrypted, self.user.pk)['strokes'], STROKES)
        sig.refresh_from_db()
        self.assertEqual(sig.rendered_signature, render_signature(STROKES))
        img = Image.open(BytesIO(base64.b64decode(sig.rendered_signature.split(',')[1])))
        self.assertEqual(img.size, (900, 300))
        self.assertIsNotNone(img.getbbox())

    def test_ciphertext_is_randomized_and_bound_to_owner(self):
        sig = self.signature()
        token = sig.encrypted_data
        sig.set_strokes(STROKES)
        self.assertNotEqual(sig.encrypted_data, token)
        with self.assertRaises(SignatureDecryptionError):
            decrypt_payload(token, self.user.pk + 1)

    def test_tampering_and_wrong_key_are_rejected(self):
        sig = self.signature()
        token = sig.encrypted_data
        replacement = ('A' if token[50] != 'A' else 'B')
        with self.assertRaises(SignatureDecryptionError):
            decrypt_payload(token[:50] + replacement + token[51:], self.user.pk)
        with override_settings(SIGNATURE_ENCRYPTION_KEYS=[Fernet.generate_key().decode()]):
            with self.assertRaises(SignatureDecryptionError):
                sig.rendered_signature

    def test_missing_key_never_saves_plaintext(self):
        with override_settings(SIGNATURE_ENCRYPTION_KEYS=[], SIGNATURE_ENCRYPTION_KEY_FILE=''):
            with self.assertRaises(ImproperlyConfigured):
                self.signature()
        self.assertFalse(Signature.objects.exists())

    def test_legacy_image_save_is_encrypted_and_preserved(self):
        png = render_signature(STROKES)
        sig = Signature.objects.create(user=self.user, signature=png)
        sig.refresh_from_db()
        self.assertIsNone(sig.signature)
        self.assertEqual(sig.rendered_signature, png)

    def test_existing_plaintext_records_render_and_migration_is_preview_first(self):
        sig = Signature.objects.create(user=self.user)
        png = render_signature(STROKES)
        Signature.objects.filter(pk=sig.pk).update(signature=png)
        sig.refresh_from_db()
        self.assertEqual(sig.rendered_signature, png)
        call_command('encrypt_signatures', stdout=StringIO())
        sig.refresh_from_db()
        self.assertEqual(sig.signature, png)
        call_command('encrypt_signatures', apply=True, stdout=StringIO())
        sig.refresh_from_db()
        self.assertIsNone(sig.signature)
        self.assertEqual(sig.rendered_signature, png)
        token = sig.encrypted_data
        call_command('encrypt_signatures', apply=True, stdout=StringIO())
        sig.refresh_from_db()
        self.assertEqual(sig.encrypted_data, token)

    def test_rotation_preserves_image_and_retires_old_key(self):
        sig = self.signature()
        png = sig.rendered_signature
        new_key = Fernet.generate_key().decode()
        with override_settings(SIGNATURE_ENCRYPTION_KEYS=[new_key, KEY]):
            call_command('encrypt_signatures', rotate=True, apply=True, stdout=StringIO())
        sig.refresh_from_db()
        with override_settings(SIGNATURE_ENCRYPTION_KEYS=[new_key]):
            self.assertEqual(sig.rendered_signature, png)
        with self.assertRaises(InvalidToken):
            Fernet(KEY).decrypt(sig.encrypted_data.encode())

    def test_web_form_stores_encrypted_strokes_and_preserves_aspect_ratio(self):
        form = SignatureForm({'strokes': json.dumps(STROKES), 'stroke_aspect_ratio': '2'})
        self.assertTrue(form.is_valid(), form.errors)
        sig = form.save(commit=False)
        sig.user = self.user
        sig.save()
        sig.refresh_from_db()
        self.assertEqual(decrypt_payload(sig.encrypted_data, self.user.pk)['aspect_ratio'], 2)
        self.assertEqual(sig.rendered_signature, render_signature(STROKES, 2))

    def test_empty_invalid_or_oversized_strokes_rejected(self):
        for value in ([], [[[True, .1], [.4, .7]]], [[[float('nan'), 0], [1, 1]]], [[[0, 0], [2, 1]]], [[[.5, .5]]], [[[0, 0]] * 4001], [[[0, 0]] * 4000] * 6):
            with self.subTest(value_length=len(value)), self.assertRaises(ValidationError):
                validate_strokes(value)
        form = SignatureForm({'strokes': '[]'})
        self.assertFalse(form.is_valid())

    def test_pdf_receives_decrypted_image(self):
        from pdf_output.tests.test_pdf_rendering_security import render_sample
        sig = self.signature()
        with patch('pdf_output.pdf_generate_task.ImageReader') as reader:
            # Use a real ImageReader while recording calls from the actual renderer.
            from reportlab.lib.utils import ImageReader
            reader.side_effect = ImageReader
            result = render_sample('Signature', 'Owner', signature=sig.rendered_signature)
        self.assertTrue(result.startswith(b'%PDF'))
        self.assertTrue(reader.called)
