"""Authenticated signature encryption with independently managed, rotatable keys."""
import json
from pathlib import Path
from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class SignatureDecryptionError(ValueError):
    pass


def cipher():
    keys = list(getattr(settings, 'SIGNATURE_ENCRYPTION_KEYS', []))
    key_file = getattr(settings, 'SIGNATURE_ENCRYPTION_KEY_FILE', '')
    if not keys and key_file:
        try:
            keys = Path(key_file).read_text().strip().splitlines()
        except OSError:
            raise ImproperlyConfigured('Signature encryption key file is unavailable.') from None
    if not keys:
        raise ImproperlyConfigured('Configure a separate signature encryption key before saving signatures.')
    try:
        return MultiFernet([Fernet(key.strip().encode()) for key in keys if key.strip()])
    except (ValueError, TypeError):
        raise ImproperlyConfigured('Signature encryption keys are invalid.') from None


def encrypt_payload(payload, user_id):
    document = {'version': 1, 'user_id': user_id, **payload}
    return cipher().encrypt(json.dumps(document, separators=(',', ':'), allow_nan=False).encode()).decode()


def decrypt_payload(token, user_id):
    try:
        document = json.loads(cipher().decrypt(token.encode()))
        if document.get('version') != 1 or document.get('user_id') != user_id:
            raise SignatureDecryptionError('Signature could not be read.')
        return document
    except (InvalidToken, ValueError, TypeError, AttributeError):
        raise SignatureDecryptionError('Signature could not be read.') from None
