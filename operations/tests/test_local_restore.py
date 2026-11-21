from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from operations.backups import BackupError
from operations.local_database import local_database_url
from operations.local_restore import restore_local_backup, validate_manifest, _restore_environment


class LocalDatabaseURLTests(SimpleTestCase):
    def test_default_preserves_local_credentials_but_uses_separate_name(self):
        self.assertEqual(local_database_url('postgres://dev:secret@localhost:5432/direct2logbook'),
                         'postgres://dev:secret@localhost:5432/d2l_local_production')

    def test_explicit_local_copy_and_ipv6_are_supported(self):
        value = 'postgres://dev:secret@[::1]:5433/d2l_local_custom'
        self.assertEqual(local_database_url('ignored', value), value)

    def test_remote_hosts_current_app_database_services_and_options_are_rejected(self):
        for value in ('postgres://dev@prod.example/db', 'sqlite:///db.sqlite3',
                      'postgres://dev@localhost/direct2logbook', 'postgres://dev@localhost/postgres',
                      'postgres://dev@localhost/d2l_local_copy?hostaddr=104.131.19.138',
                      'postgres://dev@localhost/d2l_local_copy#fragment'):
            with self.subTest(value=value), self.assertRaises(ImproperlyConfigured):
                local_database_url('ignored', value)

    def test_remote_source_is_not_silently_reused(self):
        with self.assertRaises(ImproperlyConfigured):
            local_database_url('postgres://dev@prod.example/direct2logbook')


class LocalRestoreTests(SimpleTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = self.root / 'rclone.conf'
        self.config.write_text('[b2]\ntype=b2\n[backups]\ntype=crypt\nremote=b2:bucket\npassword=obscured-test-value\n')
        self.config.chmod(0o600)
        self.database = dict(ENGINE='django.db.backends.postgresql', HOST='localhost', PORT='5432',
                             NAME='d2l_local_copy', USER='developer', PASSWORD='secret')
        self.settings = SimpleNamespace(DATABASES={'default': self.database}, LOCAL_RESTORE_MODE=True,
            DEBUG=True, EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend',
            STRIPE_SECRET_KEY='sk_test_example', STRIPE_PUBLISHABLE_KEY='pk_test_example',
            LOCAL_RESTORE_BACKUP_REMOTE='backups:postgresql', LOCAL_RESTORE_RCLONE_CONFIG=str(self.config),
            LOCAL_RESTORE_STATE_DIR=str(self.root / 'state'))
        p = patch('operations.local_restore.settings', self.settings); p.start(); self.addCleanup(p.stop)
        p = patch('operations.local_restore.shutil.which', side_effect=lambda name: name); p.start(); self.addCleanup(p.stop)
        now = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.run_id = now.strftime('%Y%m%dT%H%M%SZ') + '-' + 'a' * 32
        self.partial = (now + timedelta(seconds=30)).strftime('%Y%m%dT%H%M%SZ') + '-' + 'b' * 32
        self.archive = b'PGDMP-local-restore-test'
        self.manifest = dict(run_id=self.run_id, created_at=now.isoformat(), verified_at=now.isoformat(),
            bytes=len(self.archive), sha256=hashlib.sha256(self.archive).hexdigest(), verification='downloaded-and-hash-matched')
        self.corrupt = False
        self.calls = []
        p = patch('operations.local_restore._run', side_effect=self.run_command); self.runner = p.start(); self.addCleanup(p.stop)
        p = patch('operations.local_restore._connection'); self.connection = p.start(); self.addCleanup(p.stop)

    def run_command(self, args, env=None, timeout=3600):
        self.calls.append((args, env))
        if '--dirs-only' in args:
            return json.dumps([{'Name': self.partial}, {'Name': self.run_id}, {'Name': 'unrelated'}])
        if '--files-only' in args:
            return '[]' if args[-2].endswith(self.partial) else json.dumps([
                {'Name': 'database.dump', 'Size': self.manifest['bytes']}, {'Name': 'manifest.json', 'Size': 300}])
        if 'cat' in args:
            return json.dumps(self.manifest)
        if 'copyto' in args:
            Path(args[-1]).write_bytes(b'corrupt' if self.corrupt else self.archive)
            return ''
        if args[0] == 'pg_restore':
            return '; Valid archive listing'
        raise AssertionError(args)

    def test_preview_finds_latest_verified_skips_partial_and_never_connects_to_database(self):
        result = restore_local_backup()
        self.assertFalse(result['applied'])
        self.assertTrue(result['backup'].endswith(self.run_id))
        self.assertEqual(result['sha256'], self.manifest['sha256'])
        self.connection.assert_not_called()
        self.assertFalse(any('delete' in arg or 'purge' in arg for args, _ in self.calls for arg in args))
        self.assertEqual([p.name for p in (self.root / 'state').iterdir()], ['restore.lock'])

    def test_checksum_mismatch_never_reaches_database(self):
        self.corrupt = True
        with self.assertRaisesRegex(BackupError, 'SHA-256'):
            restore_local_backup(apply=True, replace=True)
        self.connection.assert_not_called()

    def test_invalid_completed_manifest_does_not_fall_back_silently(self):
        self.manifest['verification'] = 'not-verified'
        with self.assertRaisesRegex(BackupError, 'manifest'):
            restore_local_backup(apply=True)
        self.connection.assert_not_called()

    def test_manifest_rejects_wrong_id_naive_time_future_verification_and_invalid_digest(self):
        for change in ({'run_id': '../other'}, {'created_at': '2026-01-01T00:00:00'},
                       {'verified_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()},
                       {'sha256': 'wrong'}, {'bytes': True}, {'bytes': 0}):
            with self.subTest(change=change), self.assertRaises(BackupError):
                validate_manifest({**self.manifest, **change}, self.run_id)

    def test_production_settings_or_live_stripe_keys_are_rejected_before_cloud_access(self):
        for key, value in [('LOCAL_RESTORE_MODE', False), ('DEBUG', False),
                           ('STRIPE_SECRET_KEY', 'sk_live_test'),
                           ('EMAIL_BACKEND', 'anymail.backends.mailgun.EmailBackend')]:
            original = getattr(self.settings, key)
            setattr(self.settings, key, value)
            with self.subTest(key=key), self.assertRaises(BackupError):
                restore_local_backup(apply=True)
            setattr(self.settings, key, original)
        self.runner.assert_not_called()
        self.connection.assert_not_called()

    def test_nonlocal_or_existing_app_database_cannot_be_targeted(self):
        for change in ({'HOST': 'prod.example'}, {'NAME': 'direct2logbook'}, {'OPTIONS': {'service': 'production'}}):
            self.settings.DATABASES = {'default': {**self.database, **change}}
            with self.subTest(change=change), self.assertRaises(BackupError):
                restore_local_backup(apply=True)
        self.runner.assert_not_called()

    def test_private_config_and_encrypted_backup_remote_are_required(self):
        self.config.chmod(0o644)
        with self.assertRaisesRegex(BackupError, '600'):
            restore_local_backup()
        self.config.chmod(0o600)
        self.config.write_text(self.config.read_text() + 'no_data_encryption=true\n')
        with self.assertRaisesRegex(BackupError, 'encrypted'):
            restore_local_backup()
        self.runner.assert_not_called()

    def test_apply_restores_new_stage_then_promotes_only_after_verification(self):
        cursor = self.connection.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ('127.0.0.1',)
        counts = {'auth_user': 3, 'flights_flight': 151, 'django_migrations': 200}
        with patch('operations.local_restore._exists', return_value=False), \
             patch('operations.local_restore.verify_restored_database', return_value=counts), \
             patch('operations.local_restore._promote', return_value=None) as promote:
            result = restore_local_backup(apply=True)
        self.assertTrue(result['applied'])
        self.assertEqual(result['table_counts'], counts)
        self.assertIsNone(result['previous_database'])
        promote.assert_called_once()
        restores = [(args, env) for args, env in self.calls if '--single-transaction' in args]
        self.assertEqual(len(restores), 1)
        args, env = restores[0]
        self.assertIn('--exit-on-error', args)
        self.assertIn('--no-owner', args)
        self.assertNotIn('--clean', args)
        self.assertTrue(env['PGDATABASE'].startswith('d2l_local_stage_'))
        self.assertNotIn('secret', ' '.join(args))
        self.assertTrue((self.root / 'state' / 'last-restore.json').exists())

    def test_failed_restore_never_promotes_or_records_success(self):
        cursor = self.connection.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ('127.0.0.1',)
        original = self.run_command
        def fail(args, **kwargs):
            if '--single-transaction' in args:
                raise BackupError('pg_restore exited with status 1.')
            return original(args, **kwargs)
        with patch('operations.local_restore._exists', return_value=False), \
             patch('operations.local_restore._run', side_effect=fail), \
             patch('operations.local_restore._promote') as promote:
            with self.assertRaises(BackupError):
                restore_local_backup(apply=True, replace=True)
        promote.assert_not_called()
        self.assertFalse((self.root / 'state' / 'last-restore.json').exists())
        queries = [str(call.args[0]) for call in cursor.execute.call_args_list]
        self.assertTrue(any('DROP DATABASE' in query and 'd2l_local_stage_' in query for query in queries))
        self.assertFalse(any('DROP DATABASE' in query and 'd2l_local_copy' in query for query in queries))

    def test_existing_copy_requires_replace_flag(self):
        cursor = self.connection.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ('127.0.0.1',)
        with patch('operations.local_restore._exists', return_value=True), \
             self.assertRaisesRegex(BackupError, '--replace'):
            restore_local_backup(apply=True)

    def test_libpq_overrides_cannot_redirect_restore_and_password_stays_out_of_arguments(self):
        with patch.dict(os.environ, {'PGSERVICE': 'production', 'PGHOSTADDR': '104.131.19.138', 'PGOPTIONS': 'unsafe'}):
            env = _restore_environment(self.database, 'd2l_local_stage_test')
        self.assertNotIn('PGSERVICE', env)
        self.assertNotIn('PGHOSTADDR', env)
        self.assertNotIn('PGOPTIONS', env)
        self.assertEqual(env['PGHOST'], '127.0.0.1')
        self.assertEqual(env['PGPASSWORD'], 'secret')


class LocalSettingsTests(SimpleTestCase):
    def test_profile_forces_local_email_test_stripe_and_separate_celery_queue(self):
        root = Path(__file__).resolve().parents[2]
        env = dict(os.environ, DJANGO_SETTINGS_MODULE='logbook.settings_local_restore', DEBUG='False',
                   DATABASE_URL='postgres://developer:secret@localhost:5432/direct2logbook',
                   LOCAL_RESTORE_DATABASE_URL='postgres://developer:secret@localhost:5432/d2l_local_settings_test',
                   STRIPE_TEST_SECRET_KEY='sk_test_local_only', STRIPE_TEST_PUBLISHABLE_KEY='pk_test_local_only')
        code = '''import django,json; django.setup()
from django.conf import settings as s
from logbook.celery import app
print(json.dumps(dict(debug=s.DEBUG,email=s.EMAIL_BACKEND,name=s.DATABASES['default']['NAME'],
stripe_test=s.STRIPE_SECRET_KEY.startswith('sk_test_'), broker=app.conf.broker_url,
queue=app.conf.task_default_queue, storage=s.STORAGES['default']['BACKEND'],
beat=app.conf.beat_scheduler, backup=s.DB_BACKUP_REMOTE)))'''
        result = subprocess.run([sys.executable, '-c', code], cwd=root, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        values = json.loads(result.stdout.splitlines()[-1])
        self.assertTrue(values['debug'])
        self.assertTrue(values['stripe_test'])
        self.assertEqual(values['email'], 'django.core.mail.backends.console.EmailBackend')
        self.assertEqual(values['name'], 'd2l_local_settings_test')
        self.assertEqual(values['broker'], 'amqp://guest:guest@127.0.0.1:5672//')
        self.assertTrue(values['queue'].startswith('d2l-local-restore-'))
        self.assertEqual(values['storage'], 'django.core.files.storage.FileSystemStorage')
        self.assertEqual(values['beat'], 'celery.beat.PersistentScheduler')
        self.assertEqual(values['backup'], '')


class LocalRestoreCommandTests(SimpleTestCase):
    def test_production_settings_refuse_command_before_remote_or_database_access(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from django.test import override_settings
        with override_settings(LOCAL_RESTORE_MODE=False, DEBUG=False), \
             patch('operations.local_restore.latest_verified') as remote, \
             patch('operations.local_restore._connection') as database:
            with self.assertRaisesRegex(CommandError, 'local-only'):
                call_command('restore_local_backup', apply=True, replace=True)
        remote.assert_not_called()
        database.assert_not_called()

    def test_default_command_is_verify_only(self):
        from io import StringIO
        from django.core.management import call_command
        output = StringIO()
        result = dict(applied=False, backup='backups:postgresql/test', sha256='a' * 64, database='d2l_local_copy')
        with patch('operations.management.commands.restore_local_backup.restore_local_backup', return_value=result) as restore:
            call_command('restore_local_backup', stdout=output)
        self.assertFalse(restore.call_args.kwargs['apply'])
        self.assertFalse(restore.call_args.kwargs['replace'])
        self.assertIn('No database changed', output.getvalue())

    def test_replacement_requires_explicit_apply(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        with patch('operations.management.commands.restore_local_backup.restore_local_backup') as restore:
            with self.assertRaisesRegex(CommandError, '--replace requires --apply'):
                call_command('restore_local_backup', replace=True)
        restore.assert_not_called()

    def test_refresh_reports_restored_counts_and_retained_previous_copy(self):
        from io import StringIO
        from django.core.management import call_command
        output = StringIO()
        result = dict(applied=True, database='d2l_local_copy', previous_database='d2l_local_previous_example',
                      table_counts={'auth_user': 15, 'flights_flight': 3713})
        with patch('operations.management.commands.restore_local_backup.restore_local_backup', return_value=result) as restore:
            call_command('restore_local_backup', apply=True, replace=True, stdout=output)
        self.assertTrue(restore.call_args.kwargs['apply'])
        self.assertTrue(restore.call_args.kwargs['replace'])
        self.assertIn('3713 flights', output.getvalue())
        self.assertIn('d2l_local_previous_example', output.getvalue())
