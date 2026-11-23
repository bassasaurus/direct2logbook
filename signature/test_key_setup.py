from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from cryptography.fernet import Fernet
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from signature.models import Signature
from django.contrib.auth import get_user_model


@override_settings(SIGNATURE_ENCRYPTION_KEYS=[], SIGNATURE_ENCRYPTION_KEY_FILE='')
class SignatureKeySetupTests(TestCase):
    def test_creation_is_explicit_and_existing_key_is_reused(self):
        with TemporaryDirectory() as directory, override_settings(BASE_DIR=directory), patch('pathlib.Path.home', return_value=Path(directory)):
            env = Path(directory) / '.env'
            env.write_text('DEBUG=False\n')
            with self.assertRaises(CommandError):
                call_command('configure_signature_encryption', stdout=StringIO())
            call_command('configure_signature_encryption', create_key=True, stdout=StringIO())
            key_file = Path(directory) / '.config/direct2logbook/signature.key'
            original = key_file.read_bytes()
            Fernet(original.strip())
            self.assertEqual(key_file.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(original.decode().strip(), env.read_text())
            call_command('configure_signature_encryption', create_key=True, stdout=StringIO())
            self.assertEqual(key_file.read_bytes(), original)
            with override_settings(SIGNATURE_ENCRYPTION_KEY_FILE=str(key_file)):
                call_command('configure_signature_encryption', stdout=StringIO())

    def test_lost_key_is_not_replaced(self):
        owner = get_user_model().objects.create_user('key-recovery')
        Signature.objects.create(user=owner, encrypted_data='unreadable-but-present')
        with TemporaryDirectory() as directory, override_settings(BASE_DIR=directory), patch('pathlib.Path.home', return_value=Path(directory)):
            (Path(directory) / '.env').touch()
            with self.assertRaisesMessage(CommandError, 'Restore their original key'):
                call_command('configure_signature_encryption', create_key=True, stdout=StringIO())
            self.assertFalse((Path(directory) / '.config/direct2logbook/signature.key').exists())

    def test_configured_missing_key_never_generates_replacement(self):
        with override_settings(SIGNATURE_ENCRYPTION_KEY_FILE='/missing/signature.key'):
            from django.core.exceptions import ImproperlyConfigured
            with self.assertRaises(ImproperlyConfigured):
                call_command('configure_signature_encryption', create_key=True, stdout=StringIO())
