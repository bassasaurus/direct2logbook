"""Opt-in native pg_dump/pg_restore drill using disposable fixture databases."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase
from psycopg2 import sql

from operations.backups import BackupError, _run
from operations.local_restore import _connection, _exists, _promote, _restore_environment, restore_local_backup


@skipUnless(os.environ.get('D2L_LOCAL_RESTORE_INTEGRATION') == '1', 'Opt-in local PostgreSQL restore drill')
class LocalRestorePostgresTests(SimpleTestCase):
    def test_full_record_restore_replacement_rollback_copy_and_active_session_protection(self):
        tools = {key: shutil.which(key) for key in ('pg_dump', 'pg_restore')}
        if not all(tools.values()):
            self.skipTest('PostgreSQL client tools required')
        database = dict(settings.DATABASES['default'])
        if database.get('HOST') not in ('localhost', '127.0.0.1', '::1'):
            self.skipTest('Loopback PostgreSQL required')
        identifier = uuid.uuid4().hex[:12]
        source = 'd2l_local_fixture_' + identifier
        target = 'd2l_local_drill_' + identifier
        stage = 'd2l_local_stage_drill_' + identifier
        database['NAME'] = target
        admin = _connection(database, 'postgres')
        created = []
        try:
            with admin.cursor() as cursor:
                cursor.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(source)))
                created.append(source)
            fixture = _connection(database, source)
            try:
                with fixture.cursor() as cursor:
                    cursor.execute('''CREATE TABLE auth_user (id integer PRIMARY KEY, email text, stripe_id text, token text);
                        CREATE TABLE django_migrations (id integer PRIMARY KEY, name text);
                        CREATE TABLE flights_flight (id integer PRIMARY KEY, user_id integer REFERENCES auth_user(id),
                            duration numeric(8,1), remarks text);
                        INSERT INTO auth_user VALUES (1, 'intact@example.com', 'cus_live_value_kept', 'existing-token-kept');
                        INSERT INTO django_migrations VALUES (1, 'fixture');
                        INSERT INTO flights_flight SELECT value, 1, 1.2, 'Original remarks' FROM generate_series(1,151) value;''')
            finally:
                fixture.close()
            with tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                dump = folder / 'source.dump'
                _run([tools['pg_dump'], '--format=custom', '--file=' + str(dump)], env=_restore_environment(database, source))
                now = datetime.now(timezone.utc) - timedelta(seconds=1)
                run_id = now.strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex
                manifest = dict(run_id=run_id, created_at=now.isoformat(), verified_at=now.isoformat(),
                    verification='downloaded-and-hash-matched', bytes=dump.stat().st_size,
                    sha256=hashlib.sha256(dump.read_bytes()).hexdigest())
                state = folder / 'state'; state.mkdir(mode=0o700)
                def command(args, env=None, timeout=3600):
                    if '--dirs-only' in args:
                        return json.dumps([{'Name': run_id}])
                    if '--files-only' in args:
                        return json.dumps([{'Name': 'database.dump', 'Size': manifest['bytes']}, {'Name': 'manifest.json', 'Size': 300}])
                    if 'cat' in args:
                        return json.dumps(manifest)
                    if 'copyto' in args:
                        shutil.copyfile(dump, args[-1]); return ''
                    return _run(args, env=env, timeout=timeout)
                configuration = (database, 'backups:postgresql', folder / 'unused-config', state,
                                 dict(rclone='mock-rclone', pg_restore=tools['pg_restore']))
                with patch('operations.local_restore._configuration', return_value=configuration), \
                     patch('operations.local_restore._run', side_effect=command):
                    result = restore_local_backup(apply=True)
                    created.append(target)
                    self.assertEqual(result['table_counts']['flights_flight'], 151)
                    restored = _connection(database, target)
                    try:
                        with restored.cursor() as cursor:
                            cursor.execute('SELECT email, stripe_id, token FROM auth_user')
                            self.assertEqual(cursor.fetchone(), ('intact@example.com', 'cus_live_value_kept', 'existing-token-kept'))
                            cursor.execute('SELECT SUM(duration), COUNT(*) FROM flights_flight')
                            self.assertEqual(cursor.fetchone(), (Decimal('181.2'), 151))
                    finally:
                        restored.close()
                    replacement = restore_local_backup(apply=True, replace=True)
                    previous = replacement['previous_database']; created.append(previous)
                    with admin.cursor() as cursor:
                        cursor.execute('SELECT datallowconn FROM pg_database WHERE datname=%s', [previous])
                        self.assertFalse(cursor.fetchone()[0])
                        cursor.execute(sql.SQL('ALTER DATABASE {} WITH ALLOW_CONNECTIONS true').format(sql.Identifier(previous)))
                    previous_connection = _connection(database, previous)
                    try:
                        with previous_connection.cursor() as cursor:
                            cursor.execute('SELECT COUNT(*) FROM flights_flight')
                            self.assertEqual(cursor.fetchone()[0], 151)
                    finally:
                        previous_connection.close()
                # An open target session must prevent replacement and re-enable connections.
                with admin.cursor() as cursor:
                    cursor.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(stage)))
                    created.append(stage)
                held = _connection(database, target)
                try:
                    with admin.cursor() as cursor:
                        with self.assertRaisesRegex(BackupError, 'Stop the local-copy'):
                            _promote(cursor, stage, target, replace=True)
                        self.assertTrue(_exists(cursor, target))
                        self.assertTrue(_exists(cursor, stage))
                        cursor.execute('SELECT datallowconn FROM pg_database WHERE datname=%s', [target])
                        self.assertTrue(cursor.fetchone()[0])
                finally:
                    held.close()
        finally:
            with admin.cursor() as cursor:
                for name in reversed(created):
                    cursor.execute(sql.SQL('DROP DATABASE IF EXISTS {}').format(sql.Identifier(name)))
            admin.close()
