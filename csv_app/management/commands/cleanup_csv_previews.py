from django.core.management.base import BaseCommand
from django.utils import timezone

from csv_app.models import CSVImportBatch, CSV_PREVIEW_MAX_AGE


class Command(BaseCommand):
    help = 'Remove CSV content from unconfirmed previews older than 10 minutes. Keep confirmation receipts.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Count expired payloads without changing them.')

    def handle(self, *args, **options):
        expired = CSVImportBatch.objects.filter(
            completed=False, created_at__lte=timezone.now() - CSV_PREVIEW_MAX_AGE,
        ).exclude(content='')
        if options['dry_run']:
            self.stdout.write(f'Expired CSV preview payloads: {expired.count()}. No changes made.')
            return
        # A concurrent confirmation holds this row lock. PostgreSQL rechecks
        # completed=False after waiting, so its committed receipt is preserved.
        count = expired.update(content='')
        self.stdout.write(f'Cleared {count} expired CSV preview payload(s). Confirmation receipts retained.')
