from django.core.management.base import BaseCommand, CommandError
from operations.backups import BackupError, alert_failure, check_database_backups


class Command(BaseCommand):
    help = 'Check backup freshness and Google Drive archive presence (run hourly).'

    def add_arguments(self, parser):
        parser.add_argument('--max-age-hours', type=int, default=26)

    def handle(self, *args, **options):
        if options['max_age_hours'] <= 0:
            raise CommandError('--max-age-hours must be positive.')
        try:
            result = check_database_backups(options['max_age_hours'])
        except BackupError as exc:
            alert_failure(str(exc))
            raise CommandError(str(exc))
        except Exception:
            message = 'Unexpected backup check failure. Inspect server configuration and availability.'
            alert_failure(message)
            raise CommandError(message)
        self.stdout.write(f"Backup healthy: verified_at={result['verified_at']}; bytes={result['bytes']}")
