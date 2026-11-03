from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

MODULE = 'flights.management.commands.scheduled_airport_sync'


class ScheduledAirportSyncTests(SimpleTestCase):
    def test_monthly_job_applies_without_interaction_and_keeps_reports_separate(self):
        with TemporaryDirectory() as directory, self.settings(AIRPORT_SYNC_REPORT_DIR=directory):
            with patch(MODULE + '.call_command') as run:
                call_command('scheduled_airport_sync', stdout=StringIO())
                call_command('scheduled_airport_sync', stdout=StringIO())
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args.args, ('sync_airports',))
            self.assertTrue(run.call_args.kwargs['apply'])
            reports = [call.kwargs['report'] for call in run.call_args_list]
            self.assertNotEqual(*reports)
            self.assertEqual(reports[0].parent, Path(directory))
            self.assertRegex(reports[0].name, r'^airport-sync-\d{8}T\d{6}Z-[a-f0-9]{8}\.json$')

    @override_settings(DEBUG=False)
    def test_failure_exits_nonzero_and_reports_to_active_sentry(self):
        with TemporaryDirectory() as directory, self.settings(AIRPORT_SYNC_REPORT_DIR=directory):
            with patch(MODULE + '.call_command', side_effect=CommandError('download failed')), \
                 patch(MODULE + '.sentry_sdk.get_client') as client, \
                 patch(MODULE + '.sentry_sdk.capture_exception') as capture, \
                 patch(MODULE + '.sentry_sdk.flush'):
                client.return_value.is_active.return_value = True
                with self.assertRaisesMessage(CommandError, 'download failed'):
                    call_command('scheduled_airport_sync')
                capture.assert_called_once()

    @override_settings(DEBUG=False)
    def test_sentry_failure_does_not_hide_the_original_job_failure(self):
        with TemporaryDirectory() as directory, self.settings(AIRPORT_SYNC_REPORT_DIR=directory):
            with patch(MODULE + '.call_command', side_effect=CommandError('download failed')), \
                 patch(MODULE + '.sentry_sdk.get_client') as client, \
                 patch(MODULE + '.sentry_sdk.capture_exception', side_effect=RuntimeError('transport failed')):
                client.return_value.is_active.return_value = True
                with self.assertRaisesMessage(CommandError, 'download failed'):
                    call_command('scheduled_airport_sync')
