from django.core.management.base import BaseCommand, CommandError
from operations.backups import BackupError
from operations.local_restore import restore_local_backup


class Command(BaseCommand):
    help = ('Local development only: download and verify the latest production backup. '
            'Use --apply to restore; add --replace to refresh an existing local copy.')
    requires_system_checks = []  # The target database may not exist yet.

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Restore after download verification. Otherwise verify only.')
        parser.add_argument('--replace', action='store_true', help='Replace an existing local copy, retaining it under a rollback name.')

    def handle(self, *args, **options):
        if options['replace'] and not options['apply']:
            raise CommandError('--replace requires --apply.')
        try:
            result = restore_local_backup(apply=options['apply'], replace=options['replace'], progress=self.stdout.write)
        except BackupError as exc:
            raise CommandError(str(exc)) from None
        except (OSError, ValueError):
            raise CommandError('Local restore could not finish. Check local files and configuration; no email was sent.') from None
        if not result['applied']:
            self.stdout.write(f"Backup downloaded and verified: {result['backup']}; SHA-256={result['sha256']}. No database changed. Add --apply to restore {result['database']}.")
            return
        self.stdout.write(self.style.SUCCESS(
            f"Restored {result['database']}: {result['table_counts']['auth_user']} users, "
            f"{result['table_counts']['flights_flight']} flights. Console email; Stripe test mode."
        ))
        if result['previous_database']:
            self.stdout.write(f"Previous local copy retained: {result['previous_database']} (connections disabled).")
        self.stdout.write('Start locally: python manage.py runserver (with logbook.settings_local_restore).')
