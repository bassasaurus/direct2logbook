"""Unattended monthly reference-data refresh with a separate report per run."""
import logging
from pathlib import Path
from uuid import uuid4

import sentry_sdk
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

logger = logging.getLogger('django.operations.airports')


class Command(BaseCommand):
    help = 'Download and apply the latest airport data, retaining closed airports and writing a dated audit report.'

    def add_arguments(self, parser):
        parser.add_argument('--report-dir', type=Path, help='Override AIRPORT_SYNC_REPORT_DIR.')

    def handle(self, *args, **options):
        try:
            directory = options['report_dir'] or Path(settings.AIRPORT_SYNC_REPORT_DIR)
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            stamp = timezone.now().strftime('%Y%m%dT%H%M%SZ')
            report = directory / f'airport-sync-{stamp}-{uuid4().hex[:8]}.json'
            call_command('sync_airports', apply=True, report=report, stdout=self.stdout, stderr=self.stderr)
        except Exception as error:
            logger.warning('Monthly airport sync failed; consult the cron log and Sentry.')
            if not settings.DEBUG and sentry_sdk.get_client().is_active():
                try:
                    sentry_sdk.capture_exception(error)
                    sentry_sdk.flush(timeout=10)
                except Exception:
                    logger.warning('Airport sync failure could not be sent to Sentry.')
            if isinstance(error, CommandError):
                raise
            raise CommandError('Monthly airport sync failed. Inspect the airport sync log.') from error
