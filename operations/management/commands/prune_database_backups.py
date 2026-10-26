from django.core.management.base import BaseCommand, CommandError
from operations.backups import BackupError, alert_failure, prune_database_backups


class Command(BaseCommand):
    help = 'Preview backup retention; --apply permanently removes eligible old archives.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            candidates = prune_database_backups(apply=options['apply'])
        except BackupError as exc:
            alert_failure(str(exc))
            raise CommandError(str(exc))
        for remote in candidates:
            self.stdout.write(remote)
        self.stdout.write(f"{'Removed' if options['apply'] else 'Would remove'} {len(candidates)} backup(s). "
                          'Policy: older than 30 days; keep at least 7 verified backups.')
