from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

MODULE = 'operations.management.commands.scheduled_database_backup'


@override_settings(DEBUG=False, DB_BACKUP_SENTRY_MONITOR_SLUG='daily-database-backup')
class ScheduledBackupTests(SimpleTestCase):
    def setUp(self):
        self.output = StringIO()
        active = patch(MODULE + '.sentry_sdk.get_client')
        self.client = active.start()
        self.client.return_value.is_active.return_value = True
        self.addCleanup(active.stop)
        for name in ('capture_checkin', 'call_command', 'sentry_sdk.flush'):
            patcher = patch(MODULE + '.' + name)
            setattr(self, name.split('.')[-1], patcher.start())
            self.addCleanup(patcher.stop)
        self.capture_checkin.return_value = 'test-check-in-id'

    def run_job(self):
        call_command('scheduled_database_backup', stdout=self.output, stderr=self.output)

    def test_success_covers_backup_then_retention_with_matching_checkin_id(self):
        self.run_job()
        self.assertEqual([item.args[0] for item in self.call_command.call_args_list],
                         ['backup_database', 'prune_database_backups'])
        self.assertTrue(self.call_command.call_args.kwargs['apply'])
        first, last = self.capture_checkin.call_args_list
        self.assertEqual(first.kwargs, {'monitor_slug': 'daily-database-backup', 'status': 'in_progress'})
        self.assertEqual(last.kwargs['check_in_id'], 'test-check-in-id')
        self.assertEqual(last.kwargs['status'], 'ok')
        self.assertGreaterEqual(last.kwargs['duration'], 0)
        self.flush.assert_called_once_with(timeout=10)

    def test_backup_failure_skips_retention_and_reports_error(self):
        self.call_command.side_effect = CommandError('Backup failed')
        with self.assertRaises(CommandError):
            self.run_job()
        self.assertEqual(self.call_command.call_count, 1)
        self.assertEqual(self.capture_checkin.call_args.kwargs['status'], 'error')

    def test_retention_failure_does_not_report_success(self):
        self.call_command.side_effect = [None, CommandError('Retention failed')]
        with self.assertRaises(CommandError):
            self.run_job()
        self.assertEqual(self.capture_checkin.call_args.kwargs['status'], 'error')

    def test_unexpected_failure_is_sanitized_and_reports_error(self):
        self.call_command.side_effect = RuntimeError('private details')
        with self.assertRaisesMessage(CommandError, 'Scheduled backup failed.') as raised:
            self.run_job()
        self.assertNotIn('private details', str(raised.exception))
        self.assertEqual(self.capture_checkin.call_args.kwargs['status'], 'error')

    def test_monitoring_failure_does_not_prevent_backup_and_retention(self):
        self.capture_checkin.side_effect = RuntimeError('private transport details')
        with self.assertLogs('django.operations.backups', level='WARNING') as logs:
            self.run_job()
        self.assertEqual(self.call_command.call_count, 2)
        self.assertNotIn('private transport details', ' '.join(logs.output))

    def test_local_disabled_and_inactive_clients_never_send_checkins(self):
        with override_settings(DEBUG=True):
            self.run_job()
        with override_settings(DB_BACKUP_SENTRY_MONITOR_SLUG=''):
            self.run_job()
        self.client.return_value.is_active.return_value = False
        self.run_job()
        self.assertEqual(self.call_command.call_count, 6)
        self.capture_checkin.assert_not_called()
        self.flush.assert_not_called()
