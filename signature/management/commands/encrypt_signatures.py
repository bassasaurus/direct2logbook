"""Encrypt legacy images or rotate existing ciphertext without changing handwriting."""
from django.core.management.base import BaseCommand
from django.db import transaction
from signature.models import Signature
from signature.encryption import cipher, decrypt_payload, encrypt_payload


class Command(BaseCommand):
    help = 'Encrypt legacy signatures. Defaults to preview; --apply writes; --rotate re-encrypts existing records.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--rotate', action='store_true')

    def handle(self, *args, **options):
        cipher()  # Validate configuration even when there are no signatures to migrate.
        cipher()  # Check key availability before changing any records.
        changed = 0
        with transaction.atomic():
            for item in Signature.objects.select_for_update().order_by('pk').iterator(chunk_size=100):
                if item.signature:
                    before = item.rendered_signature
                    item.save(update_fields=['signature', 'encrypted_data'])
                elif options['rotate'] and item.encrypted_data:
                    before = item.rendered_signature
                    data = decrypt_payload(item.encrypted_data, item.user_id)
                    payload = {k: v for k, v in data.items() if k not in ('version', 'user_id')}
                    item.encrypted_data = encrypt_payload(payload, item.user_id)
                    item.save(update_fields=['encrypted_data'])
                else:
                    continue
                if item.rendered_signature != before:
                    raise RuntimeError('Signature verification failed; transaction rolled back.')
                changed += 1
            if not options['apply']:
                transaction.set_rollback(True)
        verb = 'Encrypted and verified' if options['apply'] else 'Preview: would encrypt and verify'
        self.stdout.write(f'{verb} {changed} signature(s).')
