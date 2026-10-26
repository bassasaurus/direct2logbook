from django.core.management.base import BaseCommand, CommandError
from operations.backups import BackupError, alert_failure, run_database_backup


class Command(BaseCommand):
    help = 'Create a PostgreSQL backup, upload via rclone crypt to cloud storage, and download-verify it.'

    def handle(self, *args, **options):
        try:
            result = run_database_backup()
        except BackupError as exc:
            alert_failure(str(exc))
            raise CommandError(str(exc))
        except Exception:
            message = 'Unexpected backup failure. Inspect server configuration and availability.'
            alert_failure(message)
            raise CommandError(message)
        self.stdout.write(f"Backup verified: {result['remote']}; bytes={result['bytes']}; SHA-256={result['sha256']}")
