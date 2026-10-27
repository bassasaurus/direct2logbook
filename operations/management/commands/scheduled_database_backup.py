"""One cron invocation for backup, retention, and Sentry check-ins."""
import logging
import time

import sentry_sdk
from sentry_sdk.crons import capture_checkin
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger('django.operations.backups')


def checkin(**kwargs):
    try:
        return capture_checkin(**kwargs)
    except Exception:
        # Monitoring failures must never prevent a database backup or expose secrets.
        logger.warning('Sentry backup check-in could not be submitted.')
        return None


class Command(BaseCommand):
    help = 'Run backup and retention together, reporting the outcome to an existing Sentry monitor.'

    def handle(self, *args, **options):
        slug = settings.DB_BACKUP_SENTRY_MONITOR_SLUG
        enabled = bool(slug and not settings.DEBUG and sentry_sdk.get_client().is_active())
        started = time.monotonic()
        check_in_id = checkin(monitor_slug=slug, status='in_progress') if enabled else None
        status = 'error'
        try:
            call_command('backup_database', stdout=self.stdout, stderr=self.stderr)
            call_command('prune_database_backups', apply=True, stdout=self.stdout, stderr=self.stderr)
            status = 'ok'
        except CommandError:
            raise
        except Exception:
            # Child commands handle known backup alerts; retain a nonzero, sanitized failure.
            raise CommandError('Scheduled backup failed. Inspect the backup and retention configuration.') from None
        finally:
            if enabled:
                if check_in_id:
                    checkin(monitor_slug=slug, check_in_id=check_in_id,
                            status=status, duration=time.monotonic() - started)
                try:
                    sentry_sdk.flush(timeout=10)
                except Exception:
                    logger.warning('Sentry backup check-in flush could not finish.')
