from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS
from flights.record_integrity import record_integrity_issues


class Command(BaseCommand):
    help = 'Read-only checks for blank identifiers/routes, negative hours, case-insensitive identifier duplicates duplicate summary rows, reminders, job status values matching ownership and aircraft/tailnumber agreement.'

    def add_arguments(self, parser):
        parser.add_argument('--database', default=DEFAULT_DB_ALIAS)

    def handle(self, *args, **options):
        issues = record_integrity_issues(apps, options['database'])
        if issues:
            raise CommandError('No records changed. Resolve these before migration:\n' + '\n'.join(issues))
        self.stdout.write(self.style.SUCCESS('Record integrity checks passed. No records changed.'))
