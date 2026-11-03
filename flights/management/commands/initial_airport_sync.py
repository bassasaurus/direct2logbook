"""Require a verified off-server backup before the initial airport update."""
from pathlib import Path
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Verify a fresh off-server database backup, then apply the initial airport refresh.'

    def add_arguments(self, parser):
        parser.add_argument('--report-dir', type=Path)

    def handle(self, *args, **options):
        self.stdout.write('Creating and verifying an off-server backup before airport changes...')
        call_command('backup_database', stdout=self.stdout, stderr=self.stderr)
        self.stdout.write('Backup verified. Retain the backup reference above for recovery.')
        call_command('scheduled_airport_sync', report_dir=options['report_dir'],
                     stdout=self.stdout, stderr=self.stderr)
