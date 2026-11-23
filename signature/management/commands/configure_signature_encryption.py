"""Explicit, idempotent production key provisioning before signature conversion."""
import os
import stat
from pathlib import Path
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from signature.encryption import cipher


class Command(BaseCommand):
    help = 'Validate signature keys; --create-key explicitly provisions a separate private key if unconfigured.'

    def add_arguments(self, parser):
        parser.add_argument('--create-key', action='store_true')

    def handle(self, *args, **options):
        if settings.SIGNATURE_ENCRYPTION_KEYS or settings.SIGNATURE_ENCRYPTION_KEY_FILE:
            cipher()
            self.stdout.write('Existing signature encryption configuration verified.')
            return
        if not options['create_key']:
            raise CommandError('Configure a signature key or explicitly pass --create-key.')
        env_file = Path(settings.BASE_DIR) / '.env'
        if not env_file.is_file() or env_file.is_symlink():
            raise CommandError('A regular application .env file is required for key-file configuration.')
        # Never replace a lost key after encrypted signatures have been written.
        with connection.cursor() as cursor:
            tables = connection.introspection.table_names(cursor)
            if 'signature_signature' in tables:
                columns = connection.introspection.get_table_description(cursor, 'signature_signature')
                if 'encrypted_data' in {column.name for column in columns}:
                    cursor.execute("SELECT EXISTS (SELECT 1 FROM signature_signature WHERE encrypted_data <> '')")
                    if cursor.fetchone()[0]:
                        raise CommandError('Encrypted signatures exist. Restore their original key; no key was created.')
        directory = Path.home() / '.config' / 'direct2logbook'
        if directory.is_symlink():
            raise CommandError('The signature key directory must not be a symbolic link.')
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        key_file = directory / 'signature.key'
        try:
            descriptor = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            info = key_file.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
                raise CommandError('Existing signature key must be a private, owner-only regular file.') from None
            Fernet(key_file.read_bytes().strip())
        else:
            with os.fdopen(descriptor, 'wb') as output:
                output.write(Fernet.generate_key() + b'\n')
                output.flush()
                os.fsync(output.fileno())
        # Append only the file path. The key itself is never written to .env or logs.
        with env_file.open('a') as output:
            output.write(f'\nSIGNATURE_ENCRYPTION_KEY_FILE={key_file}\n')
            output.flush()
            os.fsync(output.fileno())
        self.stdout.write('Signature key provisioned in a private file; application environment configured.')
