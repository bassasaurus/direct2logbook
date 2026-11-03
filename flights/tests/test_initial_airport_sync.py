from io import StringIO
from pathlib import Path
from unittest.mock import ANY, call, patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class InitialAirportSyncTests(SimpleTestCase):
    @patch('flights.management.commands.initial_airport_sync.call_command')
    def test_backup_precedes_sync(self, invoke):
        out, err = StringIO(), StringIO()
        call_command('initial_airport_sync', report_dir=Path('/tmp/reports'), stdout=out, stderr=err)
        self.assertEqual(invoke.call_args_list, [
            call('backup_database', stdout=ANY, stderr=ANY),
            call('scheduled_airport_sync', report_dir=Path('/tmp/reports'), stdout=ANY, stderr=ANY),
        ])

    @patch('flights.management.commands.initial_airport_sync.call_command')
    def test_failed_backup_prevents_sync(self, invoke):
        invoke.side_effect = CommandError('Backup verification failed')
        with self.assertRaisesMessage(CommandError, 'Backup verification failed'):
            call_command('initial_airport_sync', stdout=StringIO())
        self.assertEqual(invoke.call_count, 1)
        self.assertEqual(invoke.call_args.args[0], 'backup_database')

    @patch('flights.management.commands.initial_airport_sync.call_command')
    def test_sync_failure_propagates(self, invoke):
        invoke.side_effect = [None, CommandError('Airport download failed')]
        with self.assertRaisesMessage(CommandError, 'Airport download failed'):
            call_command('initial_airport_sync', stdout=StringIO())
        self.assertEqual(invoke.call_count, 2)
