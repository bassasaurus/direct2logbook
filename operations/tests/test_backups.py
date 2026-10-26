from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from operations.backups import BackupError, _lock, run_database_backup, check_database_backups


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class DatabaseBackupTests(SimpleTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.config = self.folder / 'rclone.conf'
        self.config.write_text('[drive]\ntype=drive\n[backups]\ntype=crypt\nremote=drive:Direct2Logbook-backups\npassword=obscured-test-value\nfilename_encryption=standard\n')
        self.config.chmod(0o600)
        self.state = self.folder / 'state'
        self.override = override_settings(DB_BACKUP_REMOTE='backups:', DB_BACKUP_RCLONE_CONFIG=str(self.config),
            DB_BACKUP_STATE_DIR=str(self.state), DB_BACKUP_ALERT_EMAIL='admin@example.com')
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.cloud = {}
        self.calls = []
        self.corrupt = False
        self.fail_upload = False
        paths = patch('operations.backups.shutil.which', side_effect=lambda value: value)
        paths.start()
        self.addCleanup(paths.stop)
        runner = patch('operations.backups._run', side_effect=self.run_command)
        self.runner = runner.start()
        self.addCleanup(runner.stop)

    def run_command(self, args, env=None, timeout=3600):
        self.calls.append((args, env))
        if args[0] == 'pg_dump':
            if '--version' in args:
                return 'pg_dump (PostgreSQL) 16.15\n'
            path = Path(next(value[7:] for value in args if value.startswith('--file=')))
            path.write_bytes(b'PGDMP-test-archive')
            return ''
        if args[0] == 'pg_restore':
            return '; Valid table of contents\n'
        if 'copyto' in args:
            source, dest = args[-2:]
            if source.startswith('backups:'):
                Path(dest).write_bytes(b'corrupt' if self.corrupt else self.cloud[source])
            else:
                if self.fail_upload:
                    raise BackupError('rclone exited with status 1.')
                self.cloud[dest] = Path(source).read_bytes()
            return ''
        if 'lsjson' in args:
            prefix = args[-2] + '/'
            return json.dumps([{'Name': name[len(prefix):], 'Size': len(data)}
                for name, data in self.cloud.items() if name.startswith(prefix)])
        raise AssertionError(args)

    def test_archive_round_trip_is_verified_and_plaintext_temp_files_removed(self):
        result = run_database_backup()
        self.assertEqual(result['verification'], 'downloaded-and-hash-matched')
        self.assertEqual(len(self.cloud), 2)
        self.assertEqual(json.loads((self.state / 'last-success.json').read_text())['sha256'], result['sha256'])
        self.assertEqual(set(path.name for path in self.state.iterdir()), {'backup.lock', 'last-success.json'})
        self.assertEqual(os.stat(self.state / 'last-success.json').st_mode & 0o777, 0o600)
        self.assertEqual(check_database_backups()['run_id'], result['run_id'])

    def test_backblaze_encrypted_round_trip(self):
        self.config.write_text(self.config.read_text().replace('type=drive', 'type=b2'))
        result = run_database_backup()
        self.assertEqual(check_database_backups()['run_id'], result['run_id'])

    def test_unsupported_upstream_is_rejected_before_export(self):
        self.config.write_text(self.config.read_text().replace('type=drive', 'type=local'))
        with self.assertRaises(BackupError):
            run_database_backup()
        self.runner.assert_not_called()

    def test_distinct_runs_never_overwrite_archives(self):
        a, b = run_database_backup(), run_database_backup()
        self.assertNotEqual(a['remote'], b['remote'])
        self.assertEqual(len(self.cloud), 4)

    def test_corrupt_download_cannot_record_success(self):
        self.corrupt = True
        with self.assertRaisesRegex(BackupError, 'does not match'):
            run_database_backup()
        self.assertFalse((self.state / 'last-success.json').exists())
        self.assertEqual(len(self.cloud), 1)  # Partial archive has no success manifest.

    def test_upload_failure_preserves_previous_success_record(self):
        result = run_database_backup()
        self.fail_upload = True
        with self.assertRaises(BackupError):
            run_database_backup()
        self.assertEqual(json.loads((self.state / 'last-success.json').read_text())['run_id'], result['run_id'])

    def test_unencrypted_remote_and_disabled_data_encryption_are_rejected(self):
        with override_settings(DB_BACKUP_REMOTE='drive:'):
            with self.assertRaises(BackupError):
                run_database_backup()
        self.config.write_text(self.config.read_text() + 'no_data_encryption=true\n')
        with self.assertRaises(BackupError):
            run_database_backup()
        self.runner.assert_not_called()

    def test_public_config_permissions_are_rejected(self):
        self.config.chmod(0o644)
        with self.assertRaisesRegex(BackupError, 'mode 600'):
            run_database_backup()
        self.runner.assert_not_called()

    def test_no_database_url_or_password_is_used_as_a_process_argument(self):
        run_database_backup()
        for args, env in self.calls:
            self.assertFalse(any('DATABASE_URL' in arg or 'postgres://' in arg or 'postgresql://' in arg for arg in args))
            if args[0] == 'pg_dump' and '--version' not in args:
                self.assertIn('PGDATABASE', env)
                self.assertIn('PGPASSWORD', env)

    def test_missing_tools_fail_before_export(self):
        with patch('operations.backups.shutil.which', return_value=None):
            with self.assertRaisesRegex(BackupError, 'Install'):
                run_database_backup()
        self.runner.assert_not_called()

    def test_overlapping_backups_are_rejected(self):
        self.state.mkdir(mode=0o700)
        with _lock(self.state):
            with self.assertRaisesRegex(BackupError, 'already running'):
                run_database_backup()
        self.runner.assert_not_called()

    def test_stale_or_missing_remote_archive_is_reported(self):
        run_database_backup()
        record = self.state / 'last-success.json'
        status = json.loads(record.read_text())
        status['verified_at'] = (datetime.now(timezone.utc) - timedelta(hours=27)).isoformat()
        record.write_text(json.dumps(status))
        with self.assertRaisesRegex(BackupError, 'within 26 hours'):
            check_database_backups()
        status['verified_at'] = datetime.now(timezone.utc).isoformat()
        record.write_text(json.dumps(status))
        self.cloud.pop(status['remote'] + '/database.dump')
        with self.assertRaisesRegex(BackupError, 'missing'):
            check_database_backups()

    def test_command_failure_emails_admin_without_subprocess_details(self):
        self.corrupt = True
        with self.assertRaises(CommandError):
            call_command('backup_database')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['admin@example.com'])
        self.assertIn('does not match', mail.outbox[0].body)

    def test_freshness_check_requires_an_existing_success(self):
        with self.assertRaises(CommandError):
            call_command('check_database_backups')
        self.assertEqual(len(mail.outbox), 1)

    def test_invalid_freshness_interval_is_rejected(self):
        with self.assertRaises(CommandError):
            call_command('check_database_backups', max_age_hours=0)


class RetentionPolicyTests(SimpleTestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.manifests = []
        for index in range(40):
            created = self.now - timedelta(days=index + 1)
            self.manifests.append(dict(run_id=created.strftime('%Y%m%dT%H%M%SZ') + '-' + f'{index:032x}',
                created_at=created.isoformat(), verified_at=created.isoformat(), bytes=10,
                sha256='a' * 64, verification='downloaded-and-hash-matched'))
        self.latest = self.manifests[0]['run_id']

    def select(self):
        from operations.backups import retention_candidates
        return retention_candidates(self.manifests, self.now, self.latest)

    def test_only_archives_older_than_thirty_days_are_selected(self):
        self.assertEqual(self.select(), [item['run_id'] for item in self.manifests[30:]])

    def test_seven_old_backups_remain_during_prolonged_gaps(self):
        self.manifests = self.manifests[32:]
        self.latest = self.manifests[0]['run_id']
        self.assertEqual(len(self.select()), 1)
        self.manifests = self.manifests[:7]
        self.assertEqual(self.select(), [])

    def test_malformed_manifest_and_missing_latest_stop_retention(self):
        self.manifests[-1]['run_id'] = '../other'
        with self.assertRaises(BackupError):
            self.select()
        self.manifests.pop()
        self.latest = 'missing'
        with self.assertRaises(BackupError):
            self.select()

    def test_future_and_duplicate_records_stop_retention(self):
        self.manifests.append(self.manifests[0])
        with self.assertRaises(BackupError):
            self.select()
        self.manifests.pop()
        self.manifests[0]['verified_at'] = (self.now + timedelta(days=1)).isoformat()
        with self.assertRaises(BackupError):
            self.select()

    def test_dry_run_and_apply_use_only_exact_backup_filenames(self):
        from operations.backups import prune_database_backups
        from contextlib import nullcontext
        # Avoid the exact 30-day boundary while the real clock advances.
        self.manifests.pop(29)
        config = ('backups:postgresql', Path('/private/config'), Path('/private/state'), {'rclone': 'rclone'})
        def invoke(args, timeout=120):
            if '--dirs-only' in args:
                return json.dumps([{'Name': item['run_id']} for item in self.manifests])
            if '--files-only' in args:
                return json.dumps([{'Name': 'database.dump', 'Size': 10}, {'Name': 'manifest.json', 'Size': 300}])
            if 'cat' in args:
                return json.dumps(next(item for item in self.manifests if item['run_id'] in args[-1]))
            if 'deletefile' in args:
                return ''
            raise AssertionError(args)
        with patch('operations.backups._configuration', return_value=config), \
             patch('operations.backups._lock', return_value=nullcontext()), \
             patch('operations.backups.check_database_backups', return_value={'run_id': self.latest}), \
             patch('operations.backups._run', side_effect=invoke) as runner:
            candidates = prune_database_backups()
            self.assertEqual(len(candidates), 10)
            self.assertFalse(any('deletefile' in call.args[0] for call in runner.call_args_list))
            runner.reset_mock()
            prune_database_backups(apply=True)
            deleted = [call.args[0] for call in runner.call_args_list if 'deletefile' in call.args[0]]
            self.assertEqual(len(deleted), 20)
            self.assertEqual({args[-1] for args in deleted},
                {remote + '/' + name for remote in candidates for name in ('database.dump', 'manifest.json')})
            self.assertTrue(all('--b2-hard-delete' in args for args in deleted))
