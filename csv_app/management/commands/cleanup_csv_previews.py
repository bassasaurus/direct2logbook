from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from csv_app.models import CSVImportBatch, CSV_PREVIEW_MAX_AGE, CSV_IMPORT_STALE_AFTER


class Command(BaseCommand):
    help = 'Clear expired 10-minute previews and close background imports stalled for 20 minutes.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report counts without changing requests.')

    def handle(self, *args, **options):
        now = timezone.now()
        expired = CSVImportBatch.objects.filter(
            completed=False, status=CSVImportBatch.Status.PREVIEW,
            created_at__lte=now - CSV_PREVIEW_MAX_AGE,
        ).exclude(content='')
        stalled = CSVImportBatch.objects.filter(
            completed=False, updated_at__lte=now - CSV_IMPORT_STALE_AFTER,
            status__in=[CSVImportBatch.Status.QUEUED, CSVImportBatch.Status.UNCONFIRMED,
                        CSVImportBatch.Status.PROCESSING],
        )
        if options['dry_run']:
            self.stdout.write(f'Expired CSV preview payloads: {expired.count()}. No changes made.')
            self.stdout.write(f'Stalled background imports: {stalled.count()}. No changes made.')
            return
        count = expired.update(content='')
        # Active imports hold their batch row lock for the entire transaction.
        # Skip them; a dead worker releases the lock and can be reconciled later.
        with transaction.atomic():
            ids = list(stalled.select_for_update(skip_locked=True).values_list('pk', flat=True)[:100])
            closed = CSVImportBatch.objects.filter(pk__in=ids, completed=False).update(
                status=CSVImportBatch.Status.FAILED, content='', updated_at=now,
                error_message='The import stopped before completion. No flights were imported. Upload and inspect the file again.',
            )
        self.stdout.write(f'Cleared {count} expired CSV preview payload(s). Confirmation receipts retained.')
        self.stdout.write(f'Closed {closed} stalled background import(s). No jobs requeued.')
