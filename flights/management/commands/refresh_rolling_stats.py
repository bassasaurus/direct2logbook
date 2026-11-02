from django.core.management.base import BaseCommand
from django.utils import timezone

from flights.rolling_stats import refresh_rolling_stats


class Command(BaseCommand):
    help = 'Refresh rolling flight totals and Last Flown daily, without modifying flights or lifetime totals.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Calculate without saving summary fields.')
        parser.add_argument('--user-id', type=int, help='Refresh only this user (otherwise all users).')

    def handle(self, *args, **options):
        as_of = timezone.localdate()
        counts = refresh_rolling_stats(as_of, user_id=options['user_id'], dry_run=options['dry_run'])
        if counts['skipped_total_ids']:
            ids = ', '.join(str(pk) for pk in counts['skipped_total_ids'][:30])
            self.stderr.write(self.style.WARNING(
                f"Skipped {len(counts['skipped_total_ids'])} Total row(s) with unknown categories; "
                f'rows unchanged. Review Total IDs: {ids}. Showing up to 30 IDs.'
            ))
        verb = 'Would refresh' if options['dry_run'] else 'Refreshed'
        self.stdout.write(f"{verb} rolling statistics as of {as_of}: aircraft rows={counts['stats']}, total rows={counts['totals']}.")
