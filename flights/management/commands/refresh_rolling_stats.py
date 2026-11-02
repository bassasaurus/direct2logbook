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
        verb = 'Would refresh' if options['dry_run'] else 'Refreshed'
        self.stdout.write(f"{verb} rolling statistics as of {as_of}: aircraft rows={counts['stats']}, total rows={counts['totals']}.")
